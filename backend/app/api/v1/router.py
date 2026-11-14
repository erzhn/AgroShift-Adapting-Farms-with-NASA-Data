from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    canals,
    catalog,
    chat,
    data,
    farms,
    runs,
    strategies,
)
from app.modules.water.router import router as water_router

api_router = APIRouter(prefix="/api/v1")
for module in (auth, farms, catalog, strategies, runs, canals, chat, data):
    api_router.include_router(module.router)

# Реализованные модули (каждый — у своего владельца)
api_router.include_router(water_router)
