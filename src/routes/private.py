from fastapi import APIRouter
from src.config import settings

router = APIRouter(tags=["private"], prefix="/private")

@router.get("/")
async def info():
    return settings


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/status")
async def status():
    return {"service": "running"}


@router.get("/version")
async def version():
    return {"version": settings.VERSION}



