"""
Token & mật khẩu (doc 04 §3, §8.2). Chỉ module này được import jose/passlib.

- Access token: JWT HS256, payload cố định sub/roles/did/type/iat/exp/jti.
- Refresh token: chuỗi ngẫu nhiên (opaque), DB chỉ lưu SHA-256.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError

settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash giả để verify_password vẫn tốn thời gian khi user không tồn tại (doc 04 §4.3).
_DUMMY_HASH = _pwd.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    """So khớp mật khẩu; hashed=None (user không tồn tại / chỉ OAuth) luôn False nhưng vẫn tốn CPU."""
    if hashed is None:
        _pwd.verify(plain, _DUMMY_HASH)
        return False
    return _pwd.verify(plain, hashed)


def create_access_token(*, user_id: uuid.UUID, roles: list[str], device_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "did": str(device_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Trả payload hoặc ném UnauthorizedError(token_expired | token_invalid)."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise UnauthorizedError("token_expired", "Access token đã hết hạn") from None
    except JWTError:
        raise UnauthorizedError("token_invalid", "Token không hợp lệ") from None
    if payload.get("type") != "access" or "sub" not in payload or "did" not in payload:
        raise UnauthorizedError("token_invalid", "Sai loại token")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Trả (token_gốc, sha256_hex). Chỉ lưu sha256_hex vào DB."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
