from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


class VDCSigner:
    """
    Verifiable Digital Credential signer for AP2 payment mandates.

    In development, uses a locally generated EC key pair.
    In production, replace _load_or_generate_key() with an HSM/secure enclave interface.
    """

    KEY_FILE = Path(".dev_signing_key.pem")

    def __init__(self, key_path: Path | None = None):
        self._key_path = key_path or self.KEY_FILE
        self._private_key = self._load_or_generate_key()
        self._public_key = self._private_key.public_key()

    def _load_or_generate_key(self) -> ec.EllipticCurvePrivateKey:
        if self._key_path.exists():
            with open(self._key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)

        key = ec.generate_private_key(ec.SECP256R1())
        with open(self._key_path, "wb") as f:
            f.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
        return key

    def sign(self, payload: dict[str, Any]) -> str:
        """Sign a payload dict and return a compact JWT string."""
        now = int(datetime.now(timezone.utc).timestamp())
        claims = {
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 3600,
            **payload,
        }
        return jwt.encode(claims, self._private_key, algorithm="ES256")

    def verify(self, token: str) -> dict[str, Any]:
        """Verify and decode a signed JWT. Raises jwt.InvalidTokenError on failure."""
        return jwt.decode(token, self._public_key, algorithms=["ES256"])

    def sign_payment_mandate(self, mandate_id: str, total_cents: int, currency: str, merchant_id: str) -> str:
        """Create a signed VDC authorizing the payment mandate."""
        return self.sign({
            "sub": mandate_id,
            "type": "payment_mandate_authorization",
            "total_cents": total_cents,
            "currency": currency,
            "merchant_id": merchant_id,
        })
