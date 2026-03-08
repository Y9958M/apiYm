# pydantic 模型
from pydantic import BaseModel



class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_name: str | None = None
    nick_name: str | None = None
    tel: str

class User(BaseModel):
    tel: str
    nick_name: str | None = None
    user_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str