from datetime import datetime, timedelta, timezone
from typing import Any, Annotated
from fastapi import Depends
import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi.security import OAuth2PasswordBearer
from src.config import settings

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/private/token")

def get_password_hash(password: str) -> bytes:
    """
    加密密码（bcrypt 哈希）
    :param password: 明文密码
    :return: 加密后的密码哈希（bytes 类型）
    """
    # 生成盐值（cost 因子默认12，越高越安全但越慢）
    salt = bcrypt.gensalt()
    # 哈希密码（自动处理超长密码：bcrypt 会自动截断超过72字节的部分）
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_password


def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    """
    验证密码是否匹配
    :param plain_password: 明文密码
    :param hashed_password: 加密后的密码哈希（bytes 类型）
    :return: 是否匹配的布尔值
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password)


def create_access_token(subject: str | Any, expires: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)  # type: ignore[attr-defined]
    return encoded_jwt


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    # 解密Token
    if token:
        try:
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            print("解密后的Token内容:", decoded_token)
        except jwt.PyJWTError as e:
            print(f"解密Token时出错: {e}")
    return decoded_token


