from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoService:
    def __init__(self, key: str | None = None) -> None:
        raw = key if key is not None else get_settings().encryption_key
        if not raw:
            raw = Fernet.generate_key().decode()
        if isinstance(raw, str):
            raw = raw.encode()
        self._fernet = Fernet(raw)

    def encrypt(self, plaintext: str | None) -> bytes | None:
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, token: bytes | None) -> str | None:
        if token is None:
            return None
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt stored value") from exc


_crypto: CryptoService | None = None


def get_crypto() -> CryptoService:
    global _crypto
    if _crypto is None:
        _crypto = CryptoService()
    return _crypto


def reset_crypto() -> None:
    global _crypto
    _crypto = None
