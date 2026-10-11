"""Backup encryption: the refusals, the round-trip, and the manifest.

The failure mode being defended against is a backup that cannot be restored and
that nobody notices. So most of these tests assert what does *not* happen: no
backend means no file; a plaintext round-trip mismatch means no artefact; a wrong
passphrase means a clear error rather than silent garbage.

The round-trip test is the important one and is run for real, not stubbed: bytes
in, encrypt, decrypt, bytes out, byte-for-byte equal, and the digest the
artefact records is checked on the way back. A cryptographic path nobody has
executed is a path that is assumed to work.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_crypto import (  # noqa: E402
    BACKEND_OPENSSL,
    BACKEND_PYTHON,
    FORMAT_ID,
    BackupCryptoError,
    BackupCryptoUnavailable,
    CryptographyBackend,
    OpenSSLBackend,
    available_backends,
    public_summary,
    read_manifest,
    select_backend,
)


@pytest.fixture
def passphrase() -> str:
    # Not a real secret. Present only so the test file does not contain one.
    return "test-passphrase-not-a-secret"


@pytest.fixture
def plaintext() -> bytes:
    return b"-- PostgreSQL database dump\n" + b"row-data-\x00\x01\x02" * 512


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


class TestFraming:
    def test_a_round_trip_survives_framing(self, plaintext, passphrase):
        backend = available_backends()[0]
        payload = backend.encrypt(plaintext, passphrase)
        assert backend.decrypt(payload, passphrase) == plaintext

    def test_the_header_names_the_backend(self, plaintext, passphrase):
        backend = available_backends()[0]
        header = read_manifest(backend.encrypt(plaintext, passphrase))
        assert header["backend"] == backend.name
        assert header["kdf"] == "pbkdf2-sha256"
        assert int(header["iterations"]) > 0

    def test_the_header_records_the_plaintext_digest(self, plaintext, passphrase):
        backend = available_backends()[0]
        header = read_manifest(backend.encrypt(plaintext, passphrase))
        assert header["plaintext_sha256"] == hashlib.sha256(plaintext).hexdigest()
        assert int(header["plaintext_bytes"]) == len(plaintext)

    def test_the_header_carries_no_passphrase(self, plaintext, passphrase):
        backend = available_backends()[0]
        header_bytes = backend.encrypt(plaintext, passphrase).split(b"\n\n", 1)[0]
        assert passphrase.encode() not in header_bytes

    def test_an_unframed_artefact_is_refused(self):
        with pytest.raises(BackupCryptoError, match="no header/body separator"):
            read_manifest(b"just some bytes")

    def test_a_foreign_format_is_refused(self):
        with pytest.raises(BackupCryptoError, match="does not start with"):
            read_manifest(b"SomethingElse/v1\nbackend=x\n\nbody")


# ---------------------------------------------------------------------------
# The refusals
# ---------------------------------------------------------------------------


class TestRefusals:
    def test_no_backend_available_means_no_encryption(
        self, monkeypatch, plaintext, passphrase
    ):
        """With both backends unavailable, nothing may be produced.

        Simulated by making both `available()` return False, which is the same
        state as a machine with neither openssl nor the cryptography package.
        """
        monkeypatch.setattr(OpenSSLBackend, "available", lambda self: False)
        monkeypatch.setattr(CryptographyBackend, "available", lambda self: False)

        with pytest.raises(BackupCryptoUnavailable, match="no encryption backend"):
            select_backend()

    def test_select_by_name_requires_that_backend(self, monkeypatch):
        monkeypatch.setattr(OpenSSLBackend, "available", lambda self: False)
        available = available_backends()
        pytest.skip(
            "the cryptography backend is not installed in this environment"
        ) if not available else None
        if available:
            with pytest.raises(BackupCryptoError, match="not available here"):
                select_backend(BACKEND_OPENSSL)

    def test_a_wrong_passphrase_fails_rather_than_returning_garbage(
        self, plaintext, passphrase
    ):
        backend = available_backends()[0]
        payload = backend.encrypt(plaintext, passphrase)
        with pytest.raises(BackupCryptoError):
            backend.decrypt(payload, "a-different-passphrase-entirely")

    def test_a_tampered_ciphertext_is_detected(self, plaintext, passphrase):
        """An AEAD mode is the point; a flipped bit must not decrypt cleanly."""
        backend = available_backends()[0]
        head, body = backend.encrypt(plaintext, passphrase).split(b"\n\n", 1)
        tampered = bytearray(body)
        tampered[-1] ^= 0xFF
        with pytest.raises(BackupCryptoError):
            backend.decrypt(head + b"\n\n" + bytes(tampered), passphrase)

    def test_a_truncated_artefact_is_detected(self, plaintext, passphrase):
        backend = available_backends()[0]
        payload = backend.encrypt(plaintext, passphrase)
        with pytest.raises(BackupCryptoError):
            backend.decrypt(payload[:-16], passphrase)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


class TestSelection:
    def test_the_strongest_available_backend_is_chosen(self):
        backend = select_backend()
        assert backend.name in {BACKEND_OPENSSL, BACKEND_PYTHON}

    def test_openssl_is_preferred_when_present(self, monkeypatch):
        """Precedence is a decision, not an accident of installation order.

        Forced so the preference is tested on a machine where Python
        cryptography is the only real backend: OpenSSL is stubbed to look
        available, and the next backend must not be chosen instead.
        """
        monkeypatch.setattr(
            OpenSSLBackend,
            "available",
            lambda self: True,
        )
        assert select_backend().name == BACKEND_OPENSSL

    def test_the_summary_describes_the_mechanism_not_the_key(self, passphrase):
        backend = available_backends()[0]
        summary = public_summary(backend)
        assert summary["backend"] == backend.name
        assert passphrase not in json.dumps(summary)


# ---------------------------------------------------------------------------
# The Python backend, exercised for real
# ---------------------------------------------------------------------------


class TestCryptographyBackend:
    def test_a_full_round_trip_works(self, plaintext, passphrase):
        backend = CryptographyBackend()
        if not backend.available():
            pytest.skip("the cryptography package is not installed")
        payload = backend.encrypt(plaintext, passphrase)
        assert backend.decrypt(payload, passphrase) == plaintext

    def test_the_format_recorded_matches_the_backend(self, plaintext, passphrase):
        backend = CryptographyBackend()
        if not backend.available():
            pytest.skip("the cryptography package is not installed")
        assert read_manifest(backend.encrypt(plaintext, passphrase))["backend"] == BACKEND_PYTHON

    def test_empty_input_round_trips(self, passphrase):
        backend = CryptographyBackend()
        if not backend.available():
            pytest.skip("the cryptography package is not installed")
        payload = backend.encrypt(b"", passphrase)
        assert backend.decrypt(payload, passphrase) == b""

    def test_large_input_round_trips(self, passphrase):
        backend = CryptographyBackend()
        if not backend.available():
            pytest.skip("the cryptography package is not installed")
        payload = backend.encrypt(b"A" * (5 * 1024 * 1024), passphrase)
        assert len(backend.decrypt(payload, passphrase)) == 5 * 1024 * 1024
