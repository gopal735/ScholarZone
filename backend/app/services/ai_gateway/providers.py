"""Provider adapters for the ScholarZone AI gateway.

Each adapter implements a single interface: ``generate(request) -> ProviderResult``.
Adapters are stateless with respect to a single request; configuration is
passed at construction. No adapter makes a network call unless explicitly
configured with credentials and enabled.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .capabilities import ModelSpec, ProviderHealth

logger = logging.getLogger(__name__)

#: Failure categories (closed vocabulary).
FAILURE_TIMEOUT = "timeout"
FAILURE_UNAVAILABLE = "unavailable"
FAILURE_MALFORMED = "malformed_response"
FAILURE_RATE_LIMITED = "rate_limited"
FAILURE_CAPABILITY_MISMATCH = "capability_mismatch"
FAILURE_CANCELLED = "cancelled"

PROVIDER_MODE_DISABLED = "disabled"
PROVIDER_MODE_CONFIGURED = "configured"


@dataclass(frozen=True)
class GatewayRequest:
    """A request to a model provider."""

    system_instruction: str
    question: str
    context_blocks: tuple[str, ...]
    required_capabilities: frozenset = field(default_factory=frozenset)
    max_output_tokens: int = 400
    timeout_seconds: float | None = None
    model_override: str | None = None
    cancel_event: threading.Event | None = None


@dataclass(frozen=True)
class ProviderResult:
    """Outcome of a provider call."""

    mode: str
    used: bool = False
    text: str | None = None
    failure: str | None = None
    latency_ms: int = 0
    model: str | None = None
    provider: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None


@runtime_checkable
class ModelProvider(Protocol):
    """Interface every provider adapter implements."""

    name: str

    def generate(self, request: GatewayRequest, model: ModelSpec) -> ProviderResult: ...

    def health(self) -> ProviderHealth: ...


class DisabledProvider:
    """The production default. Reports not-used, makes no network call."""

    name = "disabled"

    def generate(self, request: GatewayRequest, model: ModelSpec) -> ProviderResult:
        return ProviderResult(mode=PROVIDER_MODE_DISABLED, used=False, failure=None)

    def generate_stream(self, request: GatewayRequest, model: ModelSpec):
        return
        yield  # make generator

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, available=True)


@dataclass
class RecordingProvider:
    """Deterministic provider for tests. Test-only: not selectable in production."""

    test_only: bool = True
    name: str = "recording"
    reply: str = "recorded"
    failure: str | None = None
    latency_ms: int = 0
    seen: list = field(default_factory=list)

    def generate(self, request: GatewayRequest, model: ModelSpec) -> ProviderResult:
        self.seen.append((request, model))
        return ProviderResult(
            mode=PROVIDER_MODE_CONFIGURED,
            used=self.failure is None,
            text=None if self.failure else self.reply,
            failure=self.failure,
            latency_ms=self.latency_ms,
            model=model.id,
            provider=self.name,
        )

    def generate_stream(self, request: GatewayRequest, model: ModelSpec):
        self.seen.append((request, model))
        if self.failure:
            raise RuntimeError(self.failure)
        # Yield in two chunks to allow incremental-streaming tests.
        text = self.reply or ""
        if not text:
            return
        mid = max(1, len(text) // 2)
        yield text[:mid]
        yield text[mid:]

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, available=True)


def credential_present(env_var: str = "SCHOLARZONE_AI_PROVIDER_KEY") -> bool:
    """Whether a credential exists for the given env var, without reading it."""
    return bool((os.getenv(env_var) or "").strip())


def sanitise_provider_error(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    if "timeout" in name or "timedout" in name:
        return FAILURE_TIMEOUT
    if "connect" in name or "network" in name:
        return FAILURE_UNAVAILABLE
    if "rate" in name or "429" in name:
        return FAILURE_RATE_LIMITED
    return FAILURE_UNAVAILABLE


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


class OpenAICompatibleProvider:
    """A genuine OpenAI-compatible chat-completions provider adapter.

    Uses only server-side configuration. Never exposes credentials.
    """

    name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = (base_url or "").rstrip("/")
        self._default_model = default_model
        self._timeout = float(timeout_seconds)
        # Security: never send credentials over plaintext HTTP (except loopback
        # in non-production). testserver is never a valid provider endpoint.
        # Full validation mirrors the factory so direct construction cannot
        # bypass the security contract.
        if self._api_key:
            try:
                from urllib.parse import urlparse
                import os as _os
                parsed = urlparse(self._base_url)
                scheme = (parsed.scheme or "").lower()
                host = (parsed.hostname or "").lower()
                production = (_os.getenv("SCHOLARZONE_ENVIRONMENT") or _os.getenv("ENVIRONMENT") or "").strip().lower() == "production"
                loopback = host in ("localhost", "127.0.0.1", "::1")
                if scheme not in ("http", "https"):
                    raise ValueError("base_url must use a supported scheme")
                if not parsed.netloc or parsed.username or parsed.password:
                    raise ValueError("base_url must not contain credentials")
                if parsed.query or parsed.fragment:
                    raise ValueError("base_url must not contain query or fragment")
                if scheme == "http":
                    if production or not loopback or host == "testserver" or host == "":
                        raise ValueError("base_url must use HTTPS when an API key is provided")
            except ValueError:
                raise

    def _model_id(self, model) -> str:
        if getattr(model, "id", None):
            return str(model.id)
        if self._default_model:
            return self._default_model
        return "gpt-4o-mini"

    def _messages(self, request: GatewayRequest) -> list[dict]:
        messages = [{"role": "system", "content": request.system_instruction}]
        for block in getattr(request, "context_blocks", ()) or ():
            messages.append({"role": "user", "content": str(block)})
        messages.append({"role": "user", "content": request.question})
        return messages

    def generate(self, request: GatewayRequest, model: ModelSpec) -> ProviderResult:
        import time as _t
        started = _t.perf_counter()
        model_id = self._model_id(model)
        payload = {
            "model": model_id,
            "messages": self._messages(request),
            "max_tokens": getattr(request, "max_output_tokens", 400) or 400,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        url = f"{self._base_url}/chat/completions"
        try:
            import httpx

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 401 or resp.status_code == 403:
                return ProviderResult(mode=PROVIDER_MODE_CONFIGURED, used=False, failure=FAILURE_UNAVAILABLE if False else "unauthorized", latency_ms=elapsed_ms(started), model=model_id, provider=self.name)
            if resp.status_code == 429:
                return ProviderResult(mode=PROVIDER_MODE_CONFIGURED, used=False, failure="rate_limited", latency_ms=elapsed_ms(started), model=model_id, provider=self.name)
            if resp.status_code >= 400:
                return ProviderResult(mode=PROVIDER_MODE_CONFIGURED, used=False, failure="unavailable", latency_ms=elapsed_ms(started), model=model_id, provider=self.name)
            data = resp.json()
            choices = data.get("choices") or []
            text = None
            if choices:
                text = (choices[0].get("message") or {}).get("content")
            usage = data.get("usage") or {}
            return ProviderResult(
                mode=PROVIDER_MODE_CONFIGURED,
                used=text is not None,
                text=text,
                failure=None if text is not None else "malformed_response",
                latency_ms=elapsed_ms(started),
                model=model_id,
                provider=self.name,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
        except Exception as exc:  # noqa: BLE001
            category = sanitise_provider_error(exc)
            return ProviderResult(mode=PROVIDER_MODE_CONFIGURED, used=False, failure=category, latency_ms=elapsed_ms(started), model=model_id, provider=self.name)

    def generate_stream(self, request: GatewayRequest, model: ModelSpec):
        """Yield incremental text chunks from an OpenAI-compatible endpoint.

        Reads bounded byte chunks, enforces absolute size/time/output limits,
        requires a terminal [DONE] marker, and raises RuntimeError with a
        stable category on failure.
        """
        import httpx
        import json as _json
        import time as _time

        model_id = self._model_id(model)
        payload = {
            "model": model_id,
            "messages": self._messages(request),
            "max_tokens": getattr(request, "max_output_tokens", 400) or 400,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json", "Accept-Encoding": "identity"}
        url = f"{self._base_url}/chat/completions"
        cancel_event = getattr(request, "cancel_event", None)
        timeout = getattr(request, "timeout_seconds", None)
        if timeout is None:
            timeout = self._timeout
        timeout = float(timeout)
        started = _time.perf_counter()
        deadline = started + timeout

        max_total_bytes = 1_000_000
        max_line_bytes = 64_000
        max_malformed = 10
        max_output_chars = max(256, (getattr(request, "max_output_tokens", 400) or 400) * 8)

        malformed_frames = 0
        saw_done = False
        output_chars = 0
        total_bytes = 0

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code in (401, 403):
                        raise RuntimeError("unauthorized")
                    if resp.status_code == 429:
                        raise RuntimeError("rate_limited")
                    if resp.status_code >= 400:
                        raise RuntimeError("unavailable")
                    content_type = (resp.headers.get("content-type") or "").lower()
                    content_encoding = (resp.headers.get("content-encoding") or "").strip().lower()
                    if content_encoding and content_encoding not in ("identity", ""):
                        raise RuntimeError("malformed_response")
                    if "text/event-stream" not in content_type and "application/json" not in content_type:
                        raise RuntimeError("malformed_response")

                    buffer = b""
                    for chunk in resp.iter_raw():
                        if cancel_event is not None and cancel_event.is_set():
                            raise RuntimeError("cancelled")
                        now = _time.perf_counter()
                        if now >= deadline:
                            raise RuntimeError("timeout")
                        total_bytes += len(chunk)
                        if total_bytes > max_total_bytes:
                            raise RuntimeError("response_too_large")
                        buffer += chunk
                        # Process complete lines.
                        while b"\n" in buffer:
                            raw_line, buffer = buffer.split(b"\n", 1)
                            if raw_line.endswith(b"\r"):
                                raw_line = raw_line[:-1]
                            if len(raw_line) > max_line_bytes:
                                raise RuntimeError("malformed_response")
                            line = raw_line.decode("utf-8", errors="replace")
                            if not line.strip():
                                continue
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if not data_str:
                                    continue
                                if data_str == "[DONE]":
                                    saw_done = True
                                    # Drain not required; break out.
                                    buffer = b""
                                    break
                                try:
                                    obj = _json.loads(data_str)
                                except Exception:
                                    malformed_frames += 1
                                    if malformed_frames > max_malformed:
                                        raise RuntimeError("malformed_response")
                                    continue
                                # Strict structure validation.
                                if not isinstance(obj, dict):
                                    malformed_frames += 1
                                    if malformed_frames > max_malformed:
                                        raise RuntimeError("malformed_response")
                                    continue
                                if "error" in obj and isinstance(obj.get("error"), (dict, str)):
                                    raise RuntimeError("provider_error")
                                choices = obj.get("choices")
                                if choices is None:
                                    choices = []
                                if not isinstance(choices, list):
                                    malformed_frames += 1
                                    if malformed_frames > max_malformed:
                                        raise RuntimeError("malformed_response")
                                    continue
                                if not choices:
                                    continue
                                choice = choices[0]
                                if not isinstance(choice, dict):
                                    malformed_frames += 1
                                    if malformed_frames > max_malformed:
                                        raise RuntimeError("malformed_response")
                                    continue
                                delta = choice.get("delta")
                                if delta is None:
                                    delta = {}
                                if not isinstance(delta, dict):
                                    malformed_frames += 1
                                    if malformed_frames > max_malformed:
                                        raise RuntimeError("malformed_response")
                                    continue
                                content = delta.get("content")
                                if content is None or content == "":
                                    # role-only or empty; skip
                                    if "role" in delta:
                                        continue
                                    # usage metadata validation
                                    usage = obj.get("usage")
                                    if usage is not None and not isinstance(usage, dict):
                                        malformed_frames += 1
                                        if malformed_frames > max_malformed:
                                            raise RuntimeError("malformed_response")
                                    continue
                                if not isinstance(content, str):
                                    malformed_frames += 1
                                    if malformed_frames > max_malformed:
                                        raise RuntimeError("malformed_response")
                                    continue
                                if output_chars + len(content) > max_output_chars:
                                    raise RuntimeError("output_limit_exceeded")
                                output_chars += len(content)
                                yield content
                            elif line.startswith(":"):
                                # SSE comment / keep-alive; ignore.
                                continue
                            else:
                                # Unknown field; ignore.
                                continue
                        if saw_done:
                            break
                        if len(buffer) > max_line_bytes:
                            raise RuntimeError("malformed_response")

                    # Process any final buffered partial line.
                    if not saw_done and buffer.strip():
                        raw_line = buffer
                        if raw_line.endswith(b"\r"):
                            raw_line = raw_line[:-1]
                        if len(raw_line) <= max_line_bytes:
                            line = raw_line.decode("utf-8", errors="replace").strip()
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str and data_str != "[DONE]":
                                    malformed_frames += 1
                                if data_str == "[DONE]":
                                    saw_done = True

                    if not saw_done:
                        raise RuntimeError("incomplete_stream")
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__.lower()
            if "timeout" in name or "timedout" in name or "readtimeout" in name:
                raise RuntimeError("timeout") from exc
            if "connect" in name or "network" in name or "reset" in name:
                raise RuntimeError("unavailable") from exc
            raise RuntimeError("unavailable") from exc

    def health(self) -> ProviderHealth:
        # Lightweight: report configured. Avoid network calls by default.
        return ProviderHealth(provider=self.name, available=bool(self._api_key))
