"""安全工具：密码哈希、JWT 令牌、对称加密"""

from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 密码加密器（惰性初始化）
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    """获取 Fernet 加密器实例（惰性初始化）。"""
    global _fernet
    if _fernet is not None:
        return _fernet
    key = settings.password_encryption_key
    if not key:
        # 未配置加密密钥时，生成一个临时密钥（重启后会失效，仅用于开发/测试）
        import warnings
        warnings.warn(
            "password_encryption_key 未配置，将使用临时密钥。"
            "生产环境必须在 .env 中设置此值。"
        )
        key = Fernet.generate_key().decode()
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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码访问令牌"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
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
