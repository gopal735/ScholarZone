"""Error classification for retry decisions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCategory:
    retryable: bool
    reason: str


NON_RETRYABLE_ERRORS: frozenset[str] = frozenset({
    "not_found",
    "forbidden",
    "invalid_url",
    "invalid_content_type",
    "client_error",
})

RETRYABLE_ERRORS: frozenset[str] = frozenset({
    "timeout",
    "connection_error",
    "rate_limited",
    "server_error",
})

TERMINAL_ERRORS: frozenset[str] = frozenset({
    "not_found",
    "forbidden",
    "invalid_url",
    "invalid_content_type",
    "client_error",
    "unexpected_error",
})


def classify_error(error_type: str) -> ErrorCategory:
    if error_type in NON_RETRYABLE_ERRORS:
        return ErrorCategory(retryable=False, reason=f"{error_type} is permanent")
    if error_type == "unexpected_error":
        return ErrorCategory(retryable=False, reason="unknown error cannot be classified")
    return ErrorCategory(retryable=True, reason=f"{error_type} is transient")


def is_retryable(error_type: str) -> bool:
    return classify_error(error_type).retryable


def is_terminal(error_type: str) -> bool:
    return error_type in TERMINAL_ERRORS
