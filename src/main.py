from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRoute
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)

# from fastapi_mcp import FastApiMCP  # type: ignore
from starlette.middleware.cors import CORSMiddleware
from .config import settings
from .route import api_router
from .core.crud import Redis,RedisError,redis_pool,create_redis_pool

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"



# 关键：将生命周期传递给 FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=None,
    redoc_url=None,
    # generate_unique_id_function=custom_generate_unique_id,
)

# 初始化Redis（绑定应用生命周期，必须在创建app后调用）
def init_redis(app: FastAPI) -> None:
    """
    初始化Redis客户端，绑定到FastAPI应用生命周期
    :param app: FastAPI应用实例
    """
    global rds

    # 应用启动：创建连接池 + 初始化Redis客户端 + 测试连接
    @app.on_event("startup")
    async def startup_redis():
        global rds
        try:
            # 创建连接池
            pool = create_redis_pool()
            # 初始化Redis客户端（绑定连接池）
            rds = Redis(connection_pool=pool)
            # 测试连接有效性（redis-py的ping为同步方法，高版本直接调用无问题）
            rds.ping()
            print(f"✅ Redis连接成功 {settings.REDIS_DSN.host}")
        except RedisError as e:
            # Redis相关异常（连接失败、认证错误等），直接终止应用
            print(f"❌ Redis连接失败：{str(e)}", exc_info=True)
            raise RuntimeError(f"Redis服务不可用：{str(e)}") from e
        except Exception as e:
            # 其他未知异常，保留栈信息
            print(f"❌ Redis初始化未知异常：{str(e)}", exc_info=True)
            raise RuntimeError(f"Redis初始化失败：{str(e)}") from e

    # 应用关闭：优雅销毁连接池，释放所有连接
    @app.on_event("shutdown")
    async def shutdown_redis():
        global redis_pool, rds
        try:
            if rds is not None:
                rds.close()  # 关闭Redis客户端
                print("Redis客户端已关闭")
            if redis_pool is not None and getattr(redis_pool, '_closed', True):
                redis_pool.disconnect()  # 销毁连接池
                redis_pool = None  # 置空，便于重启时重新创建
                print("✅ Redis连接池已优雅销毁，所有连接释放")
        except Exception as e:
            print(f"⚠️ Redis销毁过程中出现警告：{str(e)}", exc_info=True)

init_redis(app)


# Set all CORS enabled origins
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")
# 挂载 MCP 服务器


# favicon 路由
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return {"file": "static/favicon.ico"}

@app.get("/")
def root():
    # return RedirectResponse(url="/home")
    return {"message": f"Welcome to the {settings.PROJECT_NAME} {settings.ENV} application! api version: {settings.API_V1_STR}"}

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon.png",
    )

@app.get(app.swagger_ui_oauth2_redirect_url or "/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc/redoc.standalone.js",
        redoc_favicon_url="/static/redoc/favicon.png",
        with_google_fonts=False
    )

# 包含 API 路由
app.include_router(api_router, prefix=settings.API_V1_STR)   

# 创建 MCP 服务器
# mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
# mcp.mount()

