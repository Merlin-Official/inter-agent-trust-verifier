"""
Ed25519 cryptographic operations for the Inter-Agent Trust Verifier.

Provides:
- Key pair generation (Ed25519)
- Message signing
- Signature verification
- Canonical serialization for deterministic signing
"""

import json
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


def generate_keypair() -> Tuple[str, str]:
    """
    Generate a new Ed25519 key pair.

    Returns:
        Tuple of (private_key_pem, public_key_pem) as strings.
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def sign_message(private_key_pem: str, message: bytes) -> str:
    """
    Sign a message using an Ed25519 private key.

    Args:
        private_key_pem: PEM-encoded private key string.
        message: Raw bytes to sign.

    Returns:
        Hex-encoded signature string.
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Provided key is not an Ed25519 private key")

    signature = private_key.sign(message)
    return signature.hex()


def verify_signature(public_key_pem: str, message: bytes, signature_hex: str) -> bool:
    """
    Verify an Ed25519 signature.

    Args:
        public_key_pem: PEM-encoded public key string.
        message: Original message bytes.
        signature_hex: Hex-encoded signature to verify.

    Returns:
        True if signature is valid, False otherwise.
    """
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8"),
        )
        if not isinstance(public_key, Ed25519PublicKey):
            return False

        signature_bytes = bytes.fromhex(signature_hex)
        public_key.verify(signature_bytes, message)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


def canonical_json(data: dict) -> bytes:
    """
    Produce a canonical JSON representation for deterministic signing.

    Sorts keys and removes whitespace to ensure the same dict always
    produces the same byte string regardless of insertion order.

    Args:
        data: Dictionary to serialize.

    Returns:
        UTF-8 encoded canonical JSON bytes.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def get_public_key_from_private(private_key_pem: str) -> str:
    """
    Extract the public key from a private key PEM.

    Args:
        private_key_pem: PEM-encoded private key string.

    Returns:
        PEM-encoded public key string.
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    public_key = private_key.public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
