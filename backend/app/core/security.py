"""安全工具：密码哈希、JWT 令牌、对称加密"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()


# Debug: token 校验失败时，快速定位是否运行时配置发生变化（不打印 secret_key 明文）。
def _debug_jwt_config_fingerprint() -> str:
    try:
        import hashlib
        sk = settings.secret_key or ""
        algo = settings.algorithm or ""
        sk_hash = hashlib.sha256(sk.encode("utf-8")).hexdigest()[:12]
        return f"algo={algo}, secret_key_sha256[:12]={sk_hash}, secret_key_len={len(sk)}"
    except Exception:
        return "fingerprint_unavailable"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 密码加密器（惰性初始化）
_fernet: Optional[Fernet] = None


import warnings


def _get_fernet() -> Fernet:
    """获取 Fernet 加密器实例（惰性初始化）。

    如果未配置 password_encryption_key，则从 secret_key 派生稳定的密钥，
    确保加密数据在重启后仍可解密。生产环境仍建议在 .env 中显式设置。
    """
    global _fernet
    if _fernet is not None:
        return _fernet
    key = settings.password_encryption_key
    if not key:
        # 从 secret_key 派生稳定密钥，重启后仍然有效
        import base64
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"myreport-encryption-key",
        )
        derived = hkdf.derive(settings.secret_key.encode())
        key = base64.urlsafe_b64encode(derived).decode()
        warnings.warn(
            "⚠️  PASSWORD_ENCRYPTION_KEY 未设置，已从 SECRET_KEY 派生加密密钥。"
            "生产环境请显式设置 PASSWORD_ENCRYPTION_KEY。"
        )
    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


# ---------- 密码哈希 ----------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    # bcrypt 有 72 字节的限制，截断密码
    return pwd_context.hash(password[:72])


# ---------- JWT ----------


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码访问令牌"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except Exception:
        # 捕获所有 JWT 相关异常：过期、格式错误、签名错误等
        # 额外输出配置指纹，辅助定位“最后一次请求是否落到不同实例/配置”。
        try:
            logger = __import__('logging').getLogger(__name__)
            logger.debug("JWT decode failed: %s", _debug_jwt_config_fingerprint())
        except Exception:
            pass
        return None


# ---------- 对称加密（数据源密码） ----------


def encrypt_password(plaintext: str) -> str:
    """加密密码"""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    """解密密码"""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
