import httpx
import time
from datetime import datetime
from pydantic import BaseModel,HttpUrl,Field
from fastapi import APIRouter
from Crypto.Hash import MD5
from src.core.logger import HandleLog,logCall
from src.core.crud import get_redis_client
logger = HandleLog(s_name=__name__)
router = APIRouter(tags=["车辆"], prefix="/veh")
rds = get_redis_client()

DOMAIN: str = 'http://kswxp.tanway.net:6380'
API_STR = "/restPublish/restServer"
TOKEN_KEY:str = "ksswj"

LOGIN_PARAMS: dict[str, str] = {
    "username": "kszls",
    "password": "Kunshan#55"    #type params
}

def get_token_veh() -> str:
    """获取车辆相关TOKEN，优先从Redis缓存读取，缓存失效则请求接口并更新缓存"""
    token = rds.get(TOKEN_KEY)
    if token:
        t = str(token)
        logger.info(f"从Redis缓存获取到有效 {TOKEN_KEY}: {t[:10]}...")
        return t
    try:
        with httpx.Client(timeout=6) as client:
            response = client.get(
                url=f"{DOMAIN}/authcenter/userLoginExternal",
                params=LOGIN_PARAMS,
                follow_redirects=False
            )
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"请求TOKEN接口失败: {str(e)}")
        return ""
    except Exception as e:
        logger.error(f"获取TOKEN时发生未知异常: {str(e)}")
        return ""
    try:
        res_dict = response.json()
    except ValueError:
        logger.error(f"TOKEN接口响应非合法JSON，响应内容: {response.text[:500]}")
        return ""

    data = res_dict.get("data", {})
    token = data.get("token", "")
    expire_time = data.get("expireTime", 0)

    current_ts = int(time.time())
    expire_seconds = int(expire_time / 1000) - current_ts

    if token and expire_seconds > 0:
        final_expire = max(expire_seconds - 10, 10)
        rds.set(TOKEN_KEY, token, ex=final_expire)
        logger.info(f"TOKEN获取成功，已存入Redis，过期时间: {final_expire}秒，TOKEN前10位: {token[:10]}...")
        return token
    else:
        logger.warning(f"TOKEN接口返回无效数据，TOKEN: {res_dict}")
        return ""


def generate_params(code=TOKEN_KEY) -> dict:
    timestamp = datetime.fromtimestamp(int(time.time())).strftime("%Y%m%d%H%M%S")
    sign_str = code + timestamp
    md5_hash = MD5.new()
    md5_hash.update(sign_str.encode("utf-8"))
    signature = md5_hash.hexdigest().upper()  # 示例值是大写，这里转成大写
    token = get_token_veh()
    return {
        "code": code,
        "timestamp": timestamp,
        "signature": signature,
        "token": token
    }


@router.get("/list", description="车辆基础数据接口")
@logCall(logger)
async def _list():
    HEADER = {
    "Accept": "*/*","Accept-Encoding": "gzip,deflate,br","Connection": "keep-alive",
    "User-Agent": "PostmanRuntime/7.39.1",
    "content-type": "application/json"
    }
    async with httpx.AsyncClient(timeout = 12) as client:
        target_req = client.build_request(url=f"{DOMAIN}{API_STR}/veh/vehicleList", method="POST", headers=HEADER, params=generate_params(),json={})
        target_resp = await client.send(target_req)
        try:
            json_data = target_resp.json()
            json_data["proxy_url"] = target_req.url
            logger.debug(json_data)
            return json_data
        except ValueError as e:
            logger.error(f"无法将响应解析为JSON格式: {e}，响应内容: {target_resp.text}")
            return {"error": "无法将响应解析为JSON格式", "content": target_resp.text}


# token = get_token_veh()
# if token:
#     url = f"{DOMAIN}{API_STR}/veh/vehicleList"
#     response = httpx.post(url=url, headers=HEADER, params=generate_params(token), json={})
#     print(response.text)
# else:
#     logger.warning("4343")

@router.get("/")
def _get():
    # token = rds.get(TOKEN_KEY)
    token = get_token_veh()
    generate_params(token)
    return {"message": f"Welcome to the 消火栓 URL: {DOMAIN} Params: {generate_params(token)}"}



