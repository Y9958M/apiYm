from fastapi import APIRouter,Request,Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import jwt

from src.core.security import get_password_hash, verify_password,create_access_token
from src.config import settings
from src.schemas import Token,UserToken

router = APIRouter(tags=["login"], prefix="/login")
templates = Jinja2Templates(directory="static/templates")


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

def fake_decode_token(token):
    # This doesn't provide any security at all
    # Check the next version
    decoded_token = jwt.decode(
        token, settings.SECRET_KEY, algorithms=["HS256"]
    )
    username = str(decoded_token["sub"])
    user = get_user(fake_users_db, username)
    return user


@router.get("/", response_class=HTMLResponse)
def read_root(request:Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    # 这里可以添加实际的用户名和密码验证逻辑
    if username in settings.ADMIN:
        return RedirectResponse(url="/", status_code=302)
    elif username in fake_users_db:
        user = get_user(fake_users_db, username)
        if user and verify_password(password, user["hashed_password"]):
            return RedirectResponse(url="/", status_code=302)
        else:
            error_message = "Invalid username or password"
            return templates.TemplateResponse("login.html", {"request": request, "error": error_message})
    else:
        error_message = "Invalid username or password"
        return templates.TemplateResponse("login.html", {"request": request, "error": error_message})


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    return response


@router.get("/token", response_model=Token)
def login_token(username: str, password: str):
    user = get_user(fake_users_db, username)
    if not user or not verify_password(password, user["hashed_password"]):
        return {"access_token": None}
    access_token_expires = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        subject=username, expires=access_token_expires
    )
    
    return {"access_token": access_token}
    # http://127.0.0.1:8000/api/v1/login/token?username=18550994992&password=111


@router.post("/token")
def login_token_post(user: UserToken):
    print(user.model_dump())
    user_db = get_user(fake_users_db, user.username)
    if not user_db or not verify_password(user.password, user_db["hashed_password"]):
        return {"access_token": None}
    access_token_expires = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(subject=user_db, expires=access_token_expires)
    user.access_token = access_token
    # user.token = "fake-token-for-"
    return user


