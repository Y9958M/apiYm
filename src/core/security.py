import hashlib
import jwt
from jwt.exceptions import InvalidTokenError
from functools import partial
from typing import Annotated
from datetime import datetime, timedelta, timezone
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Depends, APIRouter, HTTPException, status,Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.config import settings
from src.core.db import get_db
from src.core.schemas import Token,TokenData,User,UserPublic,UserCreate
from src.core.logger import HandleLog
logger = HandleLog(s_name=__name__, console_level='DEBUG')
templates = Jinja2Templates(directory="static/templates")

router = APIRouter(tags=["login"], prefix="/login")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/token")
ALGORITHM: str = "HS256"

def hash_password(password: str) -> str:
    SALT = b"skyshy@163.com"             # 盐值（增加哈希安全性）
    pwd_bytes = (password + SALT.decode()).encode('utf-8')
    hash_result = hashlib.sha256(pwd_bytes).hexdigest()
    return hash_result

# fake_users_db = {
#     "18550994992": {
#         "tel": "18550994992",
#         "user_name": "姚鸣",
#         "nick_name": "don",
#         "hashed_password": hash_password("111"),
#         "disabled": False,
#     },
#     "13962631942": {
#         "tel": "13962631942",
#         "user_name": "alice",
#         "nick_name": "alice",
#         "hashed_password": hash_password("111"),
#         "disabled": True,
#     },
# }

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate, 
    db: AsyncSession = Depends(partial(get_db, db_name=settings.DEFAULT_DB))
):
    """
    新用户注册
    """
    # 1. 检查用户是否已存在 (根据手机号)
    statement = select(User).where(User.tel == user_in.tel)
    result = await db.exec(statement)
    existing_user = result.first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="该手机号已被注册"
        )

    # 2. 将明文密码转换为哈希密码
    # 注意：我们手动提取字段，不直接把 user_in 塞进去，因为字段名不同
    user_dict = user_in.model_dump(exclude={"password"}) # 排除明文密码
    hashed_pwd = hash_password(user_in.password)     # 加密
    
    # 3. 创建数据库对象实例
    db_user = User(**user_dict, hashed_password=hashed_pwd)
    try:
        db.add(db_user)
        await db.commit()      # 提交事务
        await db.refresh(db_user) # 刷新对象以获取数据库生成的字段（如有）
    except Exception as e:
        await db.rollback()    # 发生意外则回滚
        logger.error(f"注册用户失败: {e}")
        raise HTTPException(status_code=500, detail="数据库写入失败")

    # 5. 返回 UserPublic (FastAPI 会自动根据 response_model 过滤掉敏感字段)
    return db_user


@router.get("/users",)
async def read_users(tel: str = "13962631942",db: AsyncSession = Depends(partial(get_db, db_name=settings.DEFAULT_DB))):
    statement = select(User).where(User.tel == tel)
    result = await db.exec(statement)
    users = result.all()    # 直接 .first() 或者 .one_or_none()
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    return users

async def get_user(db, tel: str):
    result = await db.exec(select(User).where(User.tel==tel))
    user = result.first()
    return user

def create_access_token(tel:str, expires_delta: timedelta | None = None):
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    payload = {"sub":tel,"exp":expire}    
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)],
                           db: AsyncSession = Depends(partial(get_db, db_name=settings.DEFAULT_DB))):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=ALGORITHM)
        tel = payload.get("sub")
        if tel is None:
            print("tel is None")
            raise credentials_exception
        token_data = TokenData(tel=tel) 
    except InvalidTokenError:
        raise credentials_exception
    user = await get_user(db, tel=token_data.tel)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)],):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def verify_password(plain_password, hashed_password):
    return hash_password(plain_password) == hashed_password

async def authenticate_user(db, tel: str, password: str):
    user = await get_user(db, tel)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(partial(get_db, db_name=settings.DEFAULT_DB))
) -> Token:
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        tel=user.tel, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


def verify_token(token: str) -> dict | None:
    """验证Token"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=ALGORITHM)
    except jwt.ExpiredSignatureError:
        print("Token已过期")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Token无效: {e}")
        return None


@router.get("/", response_class=HTMLResponse)
def read_root(request:Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/users/me", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user


@router.get("/users/me/items")
async def read_own_items(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return [{"item_id": "Foo", "owner": current_user.user_name}]


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    return response


@router.get("/token", response_model=Token)
async def login_token(tel: str, password: str,db: AsyncSession = Depends(partial(get_db, db_name=settings.DEFAULT_DB))):
    user = await get_user(db, tel)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="手机号或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        tel=tel, expires_delta=access_token_expires
    )
    return {"access_token": access_token}
    # http://127.0.0.1:8000/api/v1/login/token?username=18550994992&password=111

