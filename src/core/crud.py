import uuid
from typing import Any,Final, Optional
import redis
from redis import ConnectionPool, Redis
from redis.exceptions import RedisError
from src.config import settings
from src.core.logger import HandleLog
logger = HandleLog(s_name=__name__, console_level='DEBUG')

# 声明全局Redis连接池和客户端变量
redis_pool: Optional[ConnectionPool] = None
rds: Optional[Redis] = None

def create_redis_pool() -> ConnectionPool:
    """创建Redis连接池（核心）"""
    global redis_pool
    if redis_pool is None or getattr(redis_pool, '_closed', False):
        redis_pool = ConnectionPool(
            host=settings.REDIS_DSN.host,
            port=settings.REDIS_DSN.port,
            password=settings.REDIS_DSN.password,
            db=int(settings.REDIS_DSN.path.strip("/")) if settings.REDIS_DSN.path else 0,
            encoding='utf-8',
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            max_connections=8,
        )
    return redis_pool

# 【新增核心函数】懒加载获取Redis客户端，增加非空校验
def get_redis_client() -> Redis:
    global rds
    if rds is None:
        # 手动触发连接池创建+客户端初始化（兼容提前调用的场景）
        try:
            pool = create_redis_pool()
            rds = Redis(connection_pool=pool)
            rds.ping()  # 测试连接有效性
            logger.info("Redis客户端懒加载初始化成功")
        except Exception as e:
            raise RuntimeError(f"获取Redis客户端失败，未完成初始化：{str(e)}") from e
    return rds


def redisConnect():
    pool = redis.ConnectionPool(
        host=settings.REDIS_DSN.host,
        port=settings.REDIS_DSN.port,
        password=settings.REDIS_DSN.password,
        db=int(settings.REDIS_DSN.path.strip("/")) if settings.REDIS_DSN.path else 0,
        decode_responses=True,
        encoding='utf-8',
        max_connections=4  # 最大连接数
    )
    r = redis.Redis(connection_pool=pool)
    try:
        r.ping()  # 发送ping，返回PONG则连接成功
        logger.info("Redis连接成功 ✅")
        return r
    except RedisError as e:
        logger.warning(f"Redis连接失败 ❌：{e}")
        return None