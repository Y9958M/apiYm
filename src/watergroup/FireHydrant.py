import httpx
from pydantic import BaseModel,Field
from fastapi import APIRouter

from src.core.logger import HandleLog,logCall
logger = HandleLog(s_name=__name__, console_level='DEBUG')
router = APIRouter(tags=["消火栓"], prefix="/fhy")

HEADER:dict = {
        "Accept": "*/*","Accept-Encoding": "gzip,deflate,br","Connection": "keep-alive",
        "User-Agent": "PostmanRuntime/7.39.1","content-type": "application/json"
    }
TARGET_URL = 'http://218.4.109.90:9031/api/openAPI'

class BaseParams(BaseModel):
    accessKey:str =Field(default="WATER_GROUP",max_length=64,description="访问秘钥")
    page:int = Field(default=1,ge=1,le=999999,description="页码")
    limit:int = Field(default=10,alias="pageSize",gt=0,le=999999,description="每页条数",)
    code:str = Field(...,max_length=16,description="设备编码")

class eqpParams(BaseParams):
    eqptType:str = Field(...,pattern=r'^\d*$',max_length=1,description="设备类型（2:消防侧盖，4:一体式消火栓）")

class plotParams(BaseParams):
    plotName:str = Field(...,max_length=16,description="小区名称")
    
@logCall(logger)
async def proxy_req(proxy_url:str,args: dict)->dict:
    async with httpx.AsyncClient() as client:
        target_req = client.build_request(url=proxy_url, method="POST", headers=HEADER, json=args)
        target_resp = await client.send(target_req)
        try:
            json_data = target_resp.json()
            json_data["proxy_url"] = target_req.url
            logger.debug(json_data)
            return json_data
        except ValueError as e:
            logger.error(f"无法将响应解析为JSON格式: {e}，响应内容: {target_resp.text}")
            return {"error": "无法将响应解析为JSON格式", "content": target_resp.text}


@router.post("/list", description="提供消火栓设备信息查询")
async def _list(params: eqpParams):
    return await proxy_req(proxy_url=f"{TARGET_URL}/xf/list",args=params.model_dump())

@router.post("/alarm",description="指定设备的报警记录信息，支持消防侧盖(eqptType=2)和一体式消火栓(eqptType=4)两种设备类型的报警记录查询。")
async def _alarm(params:eqpParams):
    return await proxy_req(proxy_url=f"{TARGET_URL}/xf/alarm",args=params.model_dump())

@router.post("/cxj",description="查询机设备查询接口")
async def _cxj(params:plotParams):
    return await proxy_req(proxy_url=f"{TARGET_URL}/cxj/list",args=params.model_dump())

@router.get("/")
def _get():
    return {"message": f"Welcome to the 消火栓 URL: {TARGET_URL}"}






