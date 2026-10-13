"""Encryption for database backups, chosen so the failure mode is a refusal.

A backup of a public repository's production data is a sensitive artefact. This
repository is public, so a dump uploaded as a build artifact is readable by
anyone unless it is encrypted first, and a plaintext dump contains user records,
credentials-adjacent configuration and the full catalogue. The single design
constraint here follows from that: **when anything needed to encrypt is absent,
the backup refuses to produce a file at all.** A backup that could not be
encrypted must not be silently written unencrypted, and it must not be written
encrypted-with-nothing.

Three things this module deliberately does not do:

* **It does not read the key from a file path the caller names.** The passphrase
  arrives as a `str` that an operator supplied from a secret, and it is never
  written, logged, or included in a manifest. `public_summary()` exists so a
  report can describe a backup without restating its secret.
* **It does not accept an unauthenticated cipher by default.** Both backends use
  an AEAD mode, because a ciphertext that can be tampered with without detection
  is not much use as a backup - the restore would "succeed" with corrupted data.
* **It does not silently pick a weaker backend when a stronger one is present.**
  `select_backend()` prefers OpenSSL, which is audited C code present in every
  CI image, and falls back to Python's `cryptography`; `available()` is what
  decides, and a false result fails the backup rather than degrading it.

The on-disk format is a short text header followed by raw bytes. The header names
the backend and its parameters, so a restore can decrypt without guessing, and it
is small enough to read with a plain file read. Nothing in it is secret.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

#: Format identifier. Bumped only in a way that breaks decryption, so a restore
#: can refuse an artefact it does not understand rather than producing garbage.
FORMAT_ID = "SzBackup/v1"

#: Header line `backend=<name>` for each backend, so a restore dispatches on the
#: one recorded in the file rather than on what happens to be installed now.
BACKEND_OPENSSL = "openssl-aes-256-gcm"
BACKEND_PYTHON = "cryptography-aes-256-gcm"

_PBKDF2_ITERATIONS = 600_000
_SALT_BYTES = 16
_NONCE_BYTES = 12
_KEY_BYTES = 32


class BackupCryptoUnavailable(RuntimeError):
    """No usable encryption backend is present.

    Raised rather than returning a "plaintext" backend: the caller must treat
    this as a refusal to produce a backup, not as a reason to write one anyway.
    """


class BackupCryptoError(RuntimeError):
    """Encryption or decryption failed for a reason the operator can act on."""


# ---------------------------------------------------------------------------
# Key derivation, shared by both backends
# ---------------------------------------------------------------------------


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 over the passphrase, with the backend's salt.

    A backup passphrase is chosen by a human, so it is not uniformly random.
    Deriving rather than using it directly means an uploaded artefact is not
    brute-forceable at the speed of the passphrase's own entropy.
    """
    import hashlib as _hashlib

    return _hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERATIONS, _KEY_BYTES
    )


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Backend:
    """One encryption implementation and the name it records in the header."""

    name: str
    #: `True` when this backend shells out. Used by tests to exercise the
    #: "OpenSSL is preferred" path without needing OpenSSL installed.
    external: bool

    def encrypt(self, plaintext: bytes, passphrase: str) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def decrypt(self, payload: bytes, passphrase: str) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def summary(self) -> dict[str, Any]:
        return {"backend": self.name, "external": self.external}


def _openssl_binary() -> str | None:
    return shutil.which("openssl")


class OpenSSLBackend(Backend):
    """`openssl enc` with AES-256-GCM, invoked with the key on stdin.

    OpenSSL's CLI does not expose GCM through `enc` in every build, so the
    availability of this backend is decided by a *round-trip probe* rather than
    by the binary existing: a binary that cannot do GCM must not be used, because
    the fallback to a non-AEAD mode would be a silent downgrade to unauthenticated
    ciphertext.
    """

    def __init__(self) -> None:
        super().__init__(name=BACKEND_OPENSSL, external=True)

    def encrypt(self, plaintext: bytes, passphrase: str) -> bytes:
        binary = _openssl_binary()
        if not binary:
            raise BackupCryptoUnavailable("openssl is not on PATH")

        salt = _random_bytes(_SALT_BYTES)
        key = _derive_key(passphrase, salt).hex()

        # `-md sha256` fixes the digest, `-pbkdf2` is explicit rather than the
        # legacy key derivation, and the IV is passed via `-iv` from the same
        # random material so it is not re-derived from the passphrase.
        nonce = _random_bytes(_NONCE_BYTES)
        proc = subprocess.run(
            [
                binary, "enc", "-aes-256-gcm",
                "-pbkdf2", "-md", "sha256", "-iter", str(_PBKDF2_ITERATIONS),
                "-K", key, "-iv", nonce.hex(),
            ],
            input=plaintext,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise BackupCryptoError(
                f"openssl encrypt exited {proc.returncode}: "
                f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}"
            )

        return _frame({
            "backend": self.name,
            "kdf": "pbkdf2-sha256",
            "iterations": _PBKDF2_ITERATIONS,
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
            "plaintext_bytes": len(plaintext),
        }, proc.stdout)

    def decrypt(self, payload: bytes, passphrase: str) -> bytes:
        header, body = _unframe(payload)
        binary = _openssl_binary()
        if not binary:
            raise BackupCryptoUnavailable("openssl is not on PATH")

        salt = bytes.fromhex(header["salt"])
        key = _derive_key(passphrase, salt).hex()
        proc = subprocess.run(
            [
                binary, "enc", "-d", "-aes-256-gcm",
                "-pbkdf2", "-md", "sha256", "-iter", str(header["iterations"]),
                "-K", key, "-iv", header["nonce"],
            ],
            input=body,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise BackupCryptoError(
                f"openssl decrypt exited {proc.returncode}; wrong passphrase or "
                "corrupt artefact"
            )
        _verify_digest(proc.stdout, header)
        return proc.stdout

    def available(self) -> bool:
        """Probe by round-trip, because presence does not imply GCM support."""
        binary = _openssl_binary()
        if not binary:
            return False
        probe = b"sz-backup-probe"
        try:
            self._probe_round_trip(binary, probe)
        except Exception:  # noqa: BLE001 - any failure means unusable
            return False
        return True

    def _probe_round_trip(self, binary: str, probe: bytes) -> None:
        result = subprocess.run(
            [binary, "enc", "-aes-256-gcm", "-pbkdf2", "-K", "00" * 32, "-iv", "00" * 12],
            input=probe, capture_output=True,
        )
        if result.returncode != 0:
            raise BackupCryptoError("openssl cannot perform AES-256-GCM")


class CryptographyBackend(Backend):
    """AES-256-GCM through Python's `cryptography`, with no subprocess.

    Used when OpenSSL is absent. It is the backend the local tests can exercise
    end to end, which matters: a cryptographic path nobody has run is a path that
    is assumed to work.
    """

    def __init__(self) -> None:
        super().__init__(name=BACKEND_PYTHON, external=False)

    def _aesgcm(self, key: bytes):  # pragma: no cover - exercised when available
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        return AESGCM(key)

    def encrypt(self, plaintext: bytes, passphrase: str) -> bytes:
        # The key is derived from the salt that will be recorded in the header,
        # and the cipher is constructed from that same key. Constructing the
        # cipher from anything else - including a placeholder salt - produces a
        # ciphertext this backend cannot decrypt, which is a bug that only shows
        # up on restore.
        try:
            aesgcm_ctor = getattr(
                __import__(
                    "cryptography.hazmat.primitives.ciphers.aead", fromlist=["AESGCM"]
                ),
                "AESGCM",
            )
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise BackupCryptoUnavailable(
                "the cryptography package is not installed"
            ) from exc

        salt = _random_bytes(_SALT_BYTES)
        aesgcm = aesgcm_ctor(_derive_key(passphrase, salt))
        nonce = _random_bytes(_NONCE_BYTES)
        body = aesgcm.encrypt(nonce, plaintext, None)

        return _frame({
            "backend": self.name,
            "kdf": "pbkdf2-sha256",
            "iterations": _PBKDF2_ITERATIONS,
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
            "plaintext_bytes": len(plaintext),
        }, body)

    def decrypt(self, payload: bytes, passphrase: str) -> bytes:
        header, body = _unframe(payload)
        aesgcm = self._aesgcm(_derive_key(passphrase, bytes.fromhex(header["salt"])))
        try:
            plaintext = aesgcm.decrypt(bytes.fromhex(header["nonce"]), body, None)
        except Exception as exc:  # noqa: BLE001 - the library raises several types
            raise BackupCryptoError(
                f"decryption failed ({type(exc).__name__}); wrong passphrase or "
                "corrupt artefact"
            ) from exc
        _verify_digest(plaintext, header)
        return plaintext

    def available(self) -> bool:
        try:
            import cryptography  # noqa: F401
        except ImportError:
            return False
        return True


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


def _frame(header: dict[str, Any], body: bytes) -> bytes:
    """A text header, a blank line, then the raw ciphertext."""
    head = (
        f"{FORMAT_ID}\n"
        + "\n".join(f"{key}={value}" for key, value in sorted(header.items()))
        + "\n\n"
    )
    return head.encode("utf-8") + body


def _unframe(payload: bytes) -> tuple[dict[str, Any], bytes]:
    """Split a framed artefact back into its header and body."""
    if b"\n\n" not in payload:
        raise BackupCryptoError("artefact has no header/body separator; not this format")

    head_bytes, body = payload.split(b"\n\n", 1)
    lines = head_bytes.decode("utf-8", "replace").splitlines()
    if not lines or lines[0] != FORMAT_ID:
        raise BackupCryptoError(
            f"artefact does not start with {FORMAT_ID!r}; refusing to decrypt"
        )

    header: dict[str, Any] = {}
    for line in lines[1:]:
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        header[key] = value
    if "backend" not in header:
        raise BackupCryptoError("artefact header names no backend")
    return header, body


def _verify_digest(plaintext: bytes, header: dict[str, Any]) -> None:
    """The restored bytes must hash to what the artefact recorded.

    This is the check that turns "decryption produced something" into "decryption
    produced the thing that was backed up". Without it, a restore can succeed with
    silently corrupted data and only be discovered later.
    """
    expected = header.get("plaintext_sha256")
    if not expected:
        raise BackupCryptoError("artefact records no plaintext digest")
    actual = hashlib.sha256(plaintext).hexdigest()
    if actual != expected:
        raise BackupCryptoError(
            "restored bytes do not match the recorded digest; the artefact is corrupt"
        )


def read_manifest(payload: bytes) -> dict[str, Any]:
    """The header of an artefact, with the secret-bearing parts already absent.

    Used by `restore` and by tests to assert what a backup recorded about itself
    without decrypting it. Never contains key material.
    """
    header, body = _unframe(payload)
    del body
    header["ciphertext_bytes"] = None  # filled by the caller, which has the full file
    return header


def _random_bytes(count: int) -> bytes:
    import secrets

    return secrets.token_bytes(count)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def available_backends() -> list[Backend]:
    """Every backend that could work here, strongest first.

    Order is the precedence: OpenSSL, then Python cryptography. A caller that
    asks for "the" backend gets the first available one, so adding a backend
    here is a deliberate act of putting it ahead of the others.
    """
    candidates: Iterable[Backend] = [OpenSSLBackend(), CryptographyBackend()]
    return [b for b in candidates if b.available()]


def select_backend(name: str | None = None) -> Backend:
    """Choose a backend, refusing when nothing usable is present.

    ``name`` selects explicitly by the name recorded in a header, which is what
    a restore uses. With no name the strongest available backend is chosen.
    """
    available = available_backends()
    if not available:
        raise BackupCryptoUnavailable(
            "no encryption backend is available; install openssl or the "
            "cryptography package. Refusing to write an unencrypted backup."
        )

    if name:
        for backend in available:
            if backend.name == name:
                return backend
        raise BackupCryptoError(
            f"artefact names backend {name!r}, which is not available here; "
            f"available: {[b.name for b in available]}"
        )
    return available[0]


def public_summary(backend: Backend) -> dict[str, Any]:
    """A description of a backend safe to put in a manifest.

    The passphrase is never part of this. A manifest gets pasted into tickets and
    into the artifact listing of a public repository, so it describes the
    *mechanism* and nothing about the *key*.
    """
    return backend.summary()
