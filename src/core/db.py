from typing import AsyncGenerator, Optional, Any, Dict, List
from urllib.parse import urlparse
from fastapi import HTTPException, Query, Header
from fastapi.exceptions import RequestValidationError
from redis import asyncio as aioredis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine,create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from src.config import settings
from src.core.logger import HandleLog
logger = HandleLog(s_name=__name__, console_level='DEBUG')


class RedisManager:
    """Redis 连接管理器"""
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None

    async def init_pool(self):
        """通过 DSN 初始化连接池"""
        if self.client:
            return
        try:
            self.client = aioredis.Redis.from_url(
                settings.RS_DSN.unicode_string(),
                encoding='utf-8',
                decode_responses=True,
                max_connections=20,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True
            )
            await self.client.ping()
            logger.info("✅ Redis 连接池初始化成功")
        except Exception as e:
            logger.error(f"❌ Redis 初始化失败: {e}")
            raise

    async def close_pool(self):
        if self.client:
            await self.client.close()
            self.client = None
            # logger.info("⚠️ Redis 连接池已关闭")

redis_manager = RedisManager()

async def get_redis() -> aioredis.Redis:
    """获取 Redis 客户端"""
    if not redis_manager.client:
        await redis_manager.init_pool()
    return redis_manager.client


class MultiDatabaseManager:
    """
    管理多个异步 SQLModel 引擎与 AsyncSession 工厂。
    """
    def __init__(self) -> None:
        self._engines: Dict[str, AsyncEngine] = {}
        self._factories: Dict[str, async_sessionmaker[AsyncSession]] = {}
        self.default_db_name = "pl" # 设置一个硬编码或来自配置的默认值

    async def init_all(self) -> None:
        """应用启动时调用，初始化所有发现的 DSN"""
        dsn_map = self._collect_dsn_map()
        for name, dsn in dsn_map.items():
            await self._init_one(name, dsn)

    async def _init_one(self, name: str, dsn: str) -> None:
        if name in self._engines:
            return
        try:
            engine = create_async_engine(
                dsn,
                echo=True if settings.LOG_LEVEL == 'DEBUG' else False,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,
            )
            # 使用 async_sessionmaker 是 SQLAlchemy 2.0 的标准用法
            factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
            )
            self._engines[name] = engine
            self._factories[name] = factory  # ⚠️ 关键：必须存入字典
            logger.info(f"✅ 数据库 '{name}' 初始化成功")
        except Exception as exc:
            logger.error(f"❌ 初始化数据库 '{name}' 失败: {exc}")
            raise

    async def close_all(self) -> None:
        for name, engine in self._engines.items():
            await engine.dispose()
        self._engines.clear()
        self._factories.clear()

    def _collect_dsn_map(self) -> Dict[str, str]:
        """扫描 settings 中以 _DSN 结尾且符合 SQL 协议的配置"""
        dsn_map = {}
        supported_schemes = {"mysql", "mysql+aiomysql", "postgresql", "postgresql+asyncpg", "sqlite", "sqlite+aiosqlite"}
        
        for attr in dir(settings):
            if attr.endswith("_DSN"):
                raw_val = getattr(settings, attr)
                if not raw_val: continue
                url_str = str(raw_val)
                try:
                    scheme = urlparse(url_str).scheme.lower()
                    if scheme in supported_schemes:
                        name = attr.removesuffix("_DSN").lower()
                        dsn_map[name] = url_str
                except: continue
        return dsn_map

    def _get_default_name(self) -> str:
        """确定默认数据库名称"""
        if self.default_db_name in self._factories:
            return self.default_db_name
        if self._factories:
            return next(iter(self._factories))
        raise RuntimeError("没有任何数据库被初始化，请检查 DSN 配置。")

db_manager = MultiDatabaseManager()

async def get_db(
    db_name: Optional[str] = None,
    db_header: Optional[str] = Header(None, alias="X-DB-Name"),
    db_query: Optional[str] = Query(None, alias="db"),
) -> AsyncGenerator[AsyncSession, None]:
    target_name = (db_name or db_header or db_query or db_manager._get_default_name()).lower()
    factory = db_manager._factories.get(target_name)
    if not factory:
        dsn_map = db_manager._collect_dsn_map()
        if target_name in dsn_map:
            await db_manager._init_one(target_name, dsn_map[target_name])
            factory = db_manager._factories.get(target_name)
        if not factory:
            raise HTTPException(status_code=400, detail=f"数据库 '{target_name}' 不存在或未配置")
    async with factory() as session:
        try:
            yield session   # 默认不在这里 commit，由业务代码显式 commit
        except (HTTPException, RequestValidationError): # 增加对校验错误的排除
            raise
        except (SQLAlchemyError, Exception) as e:   # 捕获数据库相关异常或系统崩溃异常，执行回滚
            await session.rollback()
            logger.error(f"❌ 数据库({target_name})异常，已回滚: {e}")
            raise
        finally:
            await session.close()

    # 通用数据库依赖项：支持通过参数、Header 或 Query 切换库。
    # 直接注入，逻辑会自动按 优先级（参数 > Header > Query > 默认）选择
    # 1
    # @router.get("/items")
    # async def read_items(
    #     # 直接注入，逻辑会自动按 优先级（参数 > Header > Query > 默认）选择
    #     db: AsyncSession = Depends(get_db) 
    # ):
    #     statement = select(Item)
    #     results = await db.exec(statement)
    #     return results.all()

    # 2
    # @router.post("/logs")
    # async def save_logs(
    #     # 强制指定存入 "log_db"
    #     db: AsyncSession = Depends(lambda: get_db(db_name="log_db"))
    # ):
    #     # 逻辑代码...
    #     pass
    
    # 2.1
    # from functools import partial

    # @router.post("/sync")
    # async def sync_data(
    #     # 同时注入两个不同的 Session
    #     main_db: AsyncSession = Depends(partial(get_db, db_name="primary")),
    #     read_db: AsyncSession = Depends(partial(get_db, db_name="replica"))
    # ):
    #     # 1. 从只读库查数据
    #     data = (await read_db.exec(select(Item))).all()
        
    #     # 2. 写入主库
    #     for item in data:
    #         main_db.add(item)
        
    #     await main_db.commit()
    #     return {"status": "synced"}

    # 用法：Depends(get_db) 默认库，或者 Depends(lambda: get_db(db_name="another")) # 方式三：请求头 X-DB-Name: analytics