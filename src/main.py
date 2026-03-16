from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRoute
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from contextlib import asynccontextmanager
# from fastapi_mcp import FastApiMCP  # type: ignore
from starlette.middleware.cors import CORSMiddleware
from .config import settings
from .route import api_router

from src.core.db import db_manager,redis_manager

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.init_pool()
    await db_manager.init_db()
    yield
    await redis_manager.close_pool()
    await db_manager.close_db()

# 关键：将生命周期传递给 FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
    # generate_unique_id_function=custom_generate_unique_id,
)

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

