"""Hash de senha do login por formulário (D240): scrypt da biblioteca padrão, sal por conta.

Senha em cp1252, o mesmo texto que o cliente manda. O formato guarda os parâmetros, então subir o
custo depois não invalida as contas antigas.
"""

import hashlib
import hmac
import secrets

PASSWORD_MAX_BYTES = 32  # `PASSWORD_LEN` do cliente (Core.u)
_N = 2**14
_R = 8
_P = 1
_DKLEN = 32


def check_password(password: str) -> None:
    try:
        raw = password.encode("cp1252")
    except UnicodeEncodeError as e:
        raise ValueError("senha: caractere fora do cp1252") from e
    if not 1 <= len(raw) <= PASSWORD_MAX_BYTES:
        raise ValueError(f"senha: de 1 a {PASSWORD_MAX_BYTES} caracteres")


class PasswordHasher:
    @staticmethod
    def hash(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(
            password.encode("cp1252"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
        )
        return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"

    @staticmethod
    def verify(password: str, stored: str) -> bool:
        try:
            scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
            if scheme != "scrypt":
                return False
            expected = bytes.fromhex(digest_hex)
            digest = hashlib.scrypt(
                password.encode("cp1252"),
                salt=bytes.fromhex(salt_hex),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(expected),
            )
        except ValueError, UnicodeEncodeError:
            return False
        return hmac.compare_digest(digest, expected)
