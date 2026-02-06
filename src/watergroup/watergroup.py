import httpx
from pydantic import BaseModel,HttpUrl
from fastapi import APIRouter

HEADER:dict = {
        "Accept": "*/*","Accept-Encoding": "gzip,deflate,br","Connection": "keep-alive",
        "User-Agent": "PostmanRuntime/7.39.1","content-type": "application/json"
    }

FHY_KEY="WATER_GROUP"   # 消火栓


router = APIRouter(tags=["水务集团"], prefix="/watergroup")

class WaterGroupArgs(BaseModel):
    url: HttpUrl
    accessKey: str = ""
    page:int = 1
    limit:int = 10
    description: str | None = None

@router.get("/")
def read_watergroup_root(page: int = 1, limit: int = 10):
    return {"message": "Welcome to the Water Group API"}


@router.post("/")
def post_watergroup_root(args: WaterGroupArgs):
    params = {
        "accessKey": args.accessKey, # 接入密钥
        "page": args.page,    # 当前页码
        "limit": args.limit,  # 每页数量
    }
    url = str(args.url)
    print(f"Posting to URL: {url} with params: {params}")
    response = httpx.post(url=url, json=params, headers=HEADER, timeout=6)

    return response.json()

@router.get("/cxj/list")
def get_cxj_list():
    accessKey = "WATER_GROUP"
    DOMAIN = 'http://218.4.109.90:9031'
    API_STR = "/api/openAPI/cxj"
    HEADER = {
    "Accept": "*/*","Accept-Encoding": "gzip,deflate,br","Connection": "keep-alive",
    "User-Agent": "PostmanRuntime/7.39.1",
    # "content-type": "application/json"    PostmanRuntime/7.39.1
    }
    params = {
    "accessKey": accessKey, # 接入密钥
    "page": 1,    # 当前页码
    "limit": 10,  # 每页数量
    "code": "", # 设备编码 1440958814003
    "PlotName": "", # 小区名称
    }
    response = httpx.post(url=f"{DOMAIN}{API_STR}/list", json=params, headers=HEADER, timeout=10)
    print(response.text)
    return response.json()

@router.post("/cxj/list")
def post_cxj_list():
    return {"message": "CXJ list posted"}

