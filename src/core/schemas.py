# pydantic 模型
from typing import Optional
from sqlmodel import SQLModel,Field
from pydantic import BaseModel

class MsgModel(BaseModel):
    code: int = 200
    msg: str = ''

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_name: str | None = None
    nick_name: str | None = None
    tel: str


# 1. 定义基础字段（共有字段）
class UserBase(SQLModel):
    tel: str = Field(primary_key=True, index=True, description="手机号")
    nick_name: Optional[str] = Field(default=None, description="昵称")
    user_name: Optional[str] = Field(default=None, description="用户名")
    disabled: bool = Field(default=False, description="是否禁用")

# 2. 定义数据库表模型 (包含密码)
class User(UserBase, table=True):
    __tablename__ = "users"
    hashed_password: str = Field(description="哈希密码")

# 3. 定义返回给前端的模型 (不包含密码)
class UserPublic(UserBase):
    pass  # 继承 Base 即可，自动过滤掉 hashed_password

