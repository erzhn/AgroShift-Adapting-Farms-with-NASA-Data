from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    canals,
    catalog,
    chat,
    data,
    farms,
    fields,
    runs,
    strategies,
)

api_router = APIRouter(prefix="/api/v1")
for module in (auth, farms, fields, catalog, strategies, runs, canals, chat, data):
    api_router.include_router(module.router)
