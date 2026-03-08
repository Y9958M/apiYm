from fastapi import APIRouter
from .core import security
from .config import settings
from .routes import private
from .watergroup import FireHydrant,Vehicle

api_router = APIRouter()
api_router.include_router(security.router)
api_router.include_router(FireHydrant.router)
api_router.include_router(Vehicle.router)

if settings.ENV == "DEV":
    api_router.include_router(private.router)
