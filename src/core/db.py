import json
from typing import AsyncGenerator, Optional, Any, Dict, List

from fastapi import HTTPException
from redis import asyncio as aioredis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
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
            logger.info("⚠️ Redis 连接池已关闭")

class DatabaseManager:
    """SQLModel/SQLAlchemy 异步数据库管理器"""
    def __init__(self):
        self.engine = None
        self.session_factory = None

    async def init_db(self):
        """初始化异步引擎和工厂"""
        if self.engine:
            return
        try:
            self.engine = create_async_engine(
                settings.DB_DSN.unicode_string(),
                echo=False,              # 生产环境建议 False
                pool_pre_ping=True,      # 每次从池中拿连接前先 ping，防止断开
                pool_size=10,            # 连接池基础大小
                max_overflow=20,         # 允许临时溢出的最大连接数
                pool_recycle=3600,       # 1小时强制回收连接，防止数据库端断开
            )
            
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,     # 关键：使用 SQLModel 的异步 Session
                autoflush=False,
                autocommit=False,
                expire_on_commit=False   # 异步环境下必设为 False
            )
            logger.info("✅ 数据库异步引擎初始化成功")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise

    async def close_db(self):
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            logger.info("⚠️ 数据库异步引擎已关闭")

# --- 实例化管理单例 ---
redis_manager = RedisManager()
db_manager = DatabaseManager()

# --- 依赖项 (Dependencies) ---

async def get_redis() -> aioredis.Redis:
    """获取 Redis 客户端"""
    if not redis_manager.client:
        await redis_manager.init_pool()
    return redis_manager.client

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库异步 Session"""
    if not db_manager.session_factory:
        await db_manager.init_db()
        
    async with db_manager.session_factory() as session:
        try:
            yield session
            # 默认不在这里 commit，由业务代码显式 commit
        except HTTPException:
            # 接口主动抛出的 404/401 等业务异常，不视为数据库错误，直接透传
            raise
        except (SQLAlchemyError, Exception) as e:
            # 捕获数据库相关异常或系统崩溃异常，执行回滚
            await session.rollback()
            logger.error(f"❌ 数据库操作异常，已回滚: {type(e).__name__}: {e}")
            raise
        finally:
            # 显式关闭连接
            await session.close()

