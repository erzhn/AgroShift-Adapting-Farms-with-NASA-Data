from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from agroshift_core import MODEL_VERSION
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.db.session import engine

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=MODEL_VERSION,
    description="AgroShift — система поддержки решений для хозяйств и каналов АВП. "
    "Data: NASA LaRC POWER Project.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.get("/health/db", tags=["health"])
def health_db() -> dict:
    with engine.connect() as conn:
        postgis = conn.execute(text("SELECT postgis_version()")).scalar()
    return {"status": "ok", "postgis": postgis}
