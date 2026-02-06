from fastapi import APIRouter,Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Annotated
from src.config import settings
from src.core.security import oauth2_scheme,get_password_hash,create_access_token

router = APIRouter(tags=["private"], prefix="/private")

@router.get("/")
async def info():
    return settings


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/status")
async def status():
    return {"service": "running"}


@router.get("/version")
async def version():
    return {"version": settings.VERSION}


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

@router.post("/items/")
async def create_item(item: Item,token: Annotated[str, Depends(oauth2_scheme)]):
    print(f"Token: {token}")
    return item

@router.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
    return {"token": token}


# 模拟数据库中的用户数据
fake_users_db = {
    "18550994992": {
        "username": "skyshy@example.com",
        "full_name": "Yao Ming",
        "hashed_password": get_password_hash("111"),
        "disabled": False,
    },
    "13962631942": {
        "username": "alice",
        "full_name": "Alice ",
        "hashed_password": get_password_hash("111"),
        "disabled": True,
    },
}

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return user_dict

@router.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    print(form_data)
    
    user_dict = get_user(fake_users_db, form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        subject=user_dict, expires=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}