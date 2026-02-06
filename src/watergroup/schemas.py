from pydantic import BaseModel,HttpUrl

class FhyParams(BaseModel):
    accessKey:str = "WATER_GROUP"
    page:int = 1
    limit:int = 10
    code:str=""
    eqptType:str
    pass
# params = {
#     "accessKey": accessKey, # 接入密钥
#     "page": 1,    # 当前页码
#     "limit": 10,  # 每页数量
#     "code": "", # 设备编码  302502291020
#     "eqptType": "2", # 设备类型（2：消防侧盖，4：一体式消火栓
# }
# response = httpx.post(url=url_pre("/xf/list"), json=params, headers=HEADER, timeout=10)
# print(response.url)
# print(response.text)