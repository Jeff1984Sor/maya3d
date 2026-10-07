"""Cofre de tokens de terceiros: criptografia Fernet (spec seção 0)."""

from cryptography.fernet import Fernet, InvalidToken


class TokenVaultError(Exception):
    """Chave ausente/ inválida ou token corrompido."""


class TokenVault:
    """Criptografa/decifra segredos (ex.: refresh tokens do Mercado Livre) antes de ir ao banco."""

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise TokenVaultError(
                "FERNET_KEY inválida (esperado base64 urlsafe de 32 bytes)"
            ) from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise TokenVaultError(
                "token não pôde ser decifrado (chave errada ou dado corrompido)"
            ) from exc
