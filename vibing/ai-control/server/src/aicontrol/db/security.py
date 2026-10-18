from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from aicontrol.config import get_settings

_hasher = PasswordHasher()


def _configured_encryption_key(encryption_key: str | None) -> str:
    key = encryption_key or get_settings().secret_encryption_key
    if key is None:
        raise ValueError("AIC_SECRET_ENCRYPTION_KEY must be configured to store provider keys")
    return key


def hash_secret(secret: str) -> str:
    return _hasher.hash(secret)


def verify_secret(secret_hash: str, secret: str) -> bool:
    try:
        return _hasher.verify(secret_hash, secret)
    except (VerificationError, VerifyMismatchError):
        return False


def encrypt_provider_key(api_key: str, encryption_key: str | None = None) -> str:
    key = _configured_encryption_key(encryption_key)
    return Fernet(key.encode("ascii")).encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_provider_key(encrypted_api_key: str, encryption_key: str | None = None) -> str:
    key = _configured_encryption_key(encryption_key)
    try:
        cleartext = Fernet(key.encode("ascii")).decrypt(encrypted_api_key.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("Provider key cannot be decrypted with the configured key") from exc
    return cleartext.decode("utf-8")
