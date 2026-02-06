import secrets
from typing import Annotated, Any, Literal
from pydantic import (
    AnyUrl,
    BeforeValidator,
    HttpUrl,
    MySQLDsn,
    RedisDsn,
    AmqpDsn,
    Field,
    AliasChoices,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_ignore_empty=True,
        extra="allow", # ignore
        env_file_encoding="utf-8",  # 配置文件编码
        
    )
    
    DOMAIN: HttpUrl | None  = None
    PROJECT_NAME: str = 'PROJECT_NAME'
    VERSION: str = '0.1.0'
    ENV: Literal["INIT", "PRO", "BETA","DEL","DEV","ONLINE"] = "INIT"
    LOG_LEVEL:Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL","WARN","CRI"] = "DEBUG"
    ADMIN:list[str] = ["18550994992"]
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)

    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # PG_DSN: PostgresDsn = 'postgres://postgres:@localhost:5432/postgres'     # type: ignore
    MYSQL_DSN: MySQLDsn = 'mysql+pymysql://root:@localhost:3306/Platform'    # type: ignore
    AMQP_DSN: AmqpDsn = 'amqp://user:pass@localhost:5672/'   # type: ignore
    REDIS_DSN: RedisDsn = Field('redis://:4197@localhost:6379/1',validation_alias=AliasChoices('service_redis_dsn', 'redis_url'),)   # type: ignore

    CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

settings = Settings()  # type: ignore
