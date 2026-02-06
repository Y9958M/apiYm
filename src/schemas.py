# pydantic 模型
from pydantic import BaseModel



class UserBase(BaseModel):
    username: str
    is_active: bool = True 
    is_superuser: bool = False

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    password: str | None = None

class UserInDB(UserCreate):
    hashed_password: str

    class Config:
        from_attributes = True

class User(UserBase):
    access_token: str | None = None
    pass

class Token(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"

class UserToken(UserBase):
    access_token: str | None = None
    token_type: str = "bearer"
    password: str