import uuid
import json
import inspect
from typing import Any,Optional, List, Dict
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



def data2redis(
    ds: List[Dict[str, Any]],
    ds_name: str,
    idx: str = 'id',
    batch_size: int = 100,
    expire_seconds: int = 0,
    redis_client: Optional[redis.Redis] = get_redis_client(),
) -> int:
    """
    批量将数据存入Redis Hash（优化版：移除str_list，所有值默认转为字符串）
    :param ds: 待存储的字典列表（如veh_data）
    :param ds_name: Redis Key前缀（如'veh_data'）
    :param idx: 作为Hash Key后缀的主键字段（默认'id'）
    :param batch_size: 批量插入大小，提升性能（默认100）
    :param expire_seconds: 每个Hash Key的过期时间（秒），0=永不过期（默认0）
    :param redis_client: Redis客户端实例（可选，未传入则使用默认客户端）
    :return: 总处理条数（成功+失败），失败返回0
    """
    # -------------------------- 步骤1：Redis客户端校验 --------------------------
    r = redis_client if isinstance(redis_client, redis.Redis) else None
    if not r:
        logger.error("无可用的Redis客户端（未传入且全局默认客户端初始化失败）")
        return 0
    # -------------------------- 步骤2：核心参数校验 --------------------------
    # 校验数据列表
    if not isinstance(ds, list) or len(ds) == 0:
        logger.warning("待存储数据ds为空或非列表类型，直接返回")
        return 0
    # 校验Key前缀
    if not isinstance(ds_name, str) or not ds_name.strip():
        logger.error(f"Redis Key前缀ds_name='{ds_name}' 无效（空字符串），无法执行存储")
        return 0
    ds_name = ds_name.strip()  # 去除首尾空格，避免Key格式错误
    # 校验主键字段
    if not isinstance(idx, str) or not idx.strip():
        logger.error(f"主键字段idx='{idx}' 无效（空字符串），无法生成Redis Key")
        return 0
    idx = idx.strip()
    # -------------------------- 步骤3：工具函数：值转字符串（核心优化） --------------------------
    def safe_to_str(value: Any) -> str:
        """
        安全将任意类型值转为字符串：
        1. 列表/字典 → JSON字符串（便于后续解析）
        2. None → 空字符串
        3. 其他类型 → 原生str()
        """
        if value is None:
            return ""
        elif isinstance(value, (list, dict)):
            try:
                return json.dumps(value, ensure_ascii=False)  # 保留中文
            except Exception as e:
                logger.warning(f"列表/字典JSON序列化失败，降级为str()：{e}")
                return str(value)
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, str):
            return value  # 已是字符串，直接返回
        else:
            # 处理其他类型（如datetime/对象等）
            try:
                return str(value)
            except Exception as e:
                logger.warning(f"未知类型值转换字符串失败，返回空字符串：{e}")
                return ""
    # -------------------------- 步骤4：批量处理+存储 --------------------------
    success_count = 0
    fail_count = 0
    batch_data = []
    for item_idx, item in enumerate(ds):
        # 跳过非字典数据
        if not isinstance(item, dict):
            logger.warning(f"第{item_idx}条数据非字典类型，跳过：{item}")
            fail_count += 1
            continue
        # 校验主键字段是否存在且非空
        if idx not in item or not item[idx]:
            logger.warning(f"第{item_idx}条数据缺少主键'{idx}'或值为空，跳过：{item}")
            fail_count += 1
            continue
        # 深拷贝避免修改原数据
        processed_item = item.copy()
        # -------------------------- 核心：所有字段值转为字符串 --------------------------
        for key, value in processed_item.items():
            processed_item[key] = safe_to_str(value)
        # 加入批量缓存
        batch_data.append((item[idx], processed_item))
        # 批量插入触发条件：达到批量大小 或 遍历到最后一条
        if len(batch_data) >= batch_size or item_idx == len(ds) - 1:
            for pk_value, processed in batch_data:
                # 主键值也转为字符串（避免数字主键导致Key格式不一致）
                pk_str = safe_to_str(pk_value)
                redis_key = f"{ds_name}:{pk_str}"
                try:
                    # 存入Redis Hash（所有值已是字符串，兼容Redis Hash要求）
                    r.hset(redis_key, mapping=processed)
                    # 设置过期时间
                    if expire_seconds > 0:
                        r.expire(redis_key, expire_seconds)
                    success_count += 1
                    logger.debug(f"数据存入Redis成功：{redis_key}")
                except RedisError as e:
                    logger.error(f"数据存入Redis失败（Key：{redis_key}）：{e}")
                    fail_count += 1
                except Exception as e:
                    logger.error(f"数据处理异常（Key：{redis_key}）：{e}")
                    fail_count += 1
            # 清空批量缓存
            batch_data.clear()
    total = success_count + fail_count
    logger.info(f"Redis存储完成 | 总条数：{total} | 成功：{success_count} | 失败：{fail_count}")
    return total


def redis2data(
    name: str,
    redis_client: Optional[redis.Redis] = None,
    batch_size: int = 1000,  # scan_iter批量大小，提升扫描性能
) -> dict:
    # 1.1 校验Key前缀
    if not isinstance(name, str) or not name.strip():
        logger.error("Redis Key前缀name为空字符串，无法执行读取")
        return {}
    name = name.strip()  # 去除首尾空格，避免Key格式错误
    r = redis_client if isinstance(redis_client, redis.Redis) else None
    if not r:
        logger.error("无可用的Redis客户端（未传入有效实例且默认客户端初始化失败）")
        return {}
    else:
        redis_host = r.connection_pool.connection_kwargs.get('host', '未知')
        redis_db = r.connection_pool.connection_kwargs.get('db', '未知')
        logger.debug((f"Redis 地址：{redis_host} DB: {redis_db}"))
    decode_responses = getattr(r, 'decode_responses', False)
    data_list = []
    success_count = 0
    fail_count = 0
    scan_pattern = f"{name}:*"
    try:
        for key in r.scan_iter(match=scan_pattern, count=batch_size):
            try:
                raw_data = r.hgetall(key)
                if inspect.isawaitable(raw_data):
                    import asyncio
                    raw_data = asyncio.get_event_loop().run_until_complete(raw_data)
                if not raw_data:
                    logger.debug(f"Redis Key {key} 无数据，跳过")
                    fail_count += 1
                    continue
                # -------------------------- 步骤3：编码处理（自动适配） --------------------------
                item = {}
                for k, v in raw_data.items():
                    # 处理键的编码
                    key_str = k.decode('utf-8') if isinstance(k, bytes) and not decode_responses else k
                    # 处理值的编码
                    val_str = v.decode('utf-8') if isinstance(v, bytes) and not decode_responses else v
                    item[key_str] = val_str
                data_list.append(item)
                success_count += 1
            except RedisError as e:
                logger.error(f"读取Redis Key {key} 失败：{e}")
                fail_count += 1
            except Exception as e:
                logger.error(f"处理Redis Key {key} 异常：{e}")
                fail_count += 1
    except RedisError as e:
        logger.error(f"Redis扫描Key失败（pattern：{scan_pattern}）：{e}")
    except Exception as e:
        logger.error(f"Redis数据读取整体异常：{e}")
    total_count = success_count + fail_count
    logger.info(
        f"Redis数据读取完成 | 扫描匹配Key总数：{total_count} | "
        f"成功解析：{success_count} | 失败：{fail_count} | 返回数据条数：{len(data_list)}"
    )
    return {'data_list':data_list,'total':total_count,'success_count':success_count,'fail_count':fail_count}
