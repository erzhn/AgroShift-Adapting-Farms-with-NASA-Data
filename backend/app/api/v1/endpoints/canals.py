"""Canal, supply, demand, and coordination endpoints (UC-5, FR-8.1–FR-8.6)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.canal import (
    CanalCreate,
    CanalFarmMapItem,
    CanalPlanRead,
    CanalRead,
    CoordinatePlanInput,
    ProposalResponseInput,
    SupplyRead,
    SupplyScheduleInput,
)
from app.services import canal as canal_service

router = APIRouter(tags=["canals"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/canals", response_model=list[CanalRead], summary="Список каналов АВП")
def list_canals(db: DbSession) -> list[CanalRead]:
    return canal_service.list_canals(db)


@router.post("/canals", response_model=CanalRead, status_code=status.HTTP_201_CREATED,
             summary="Создать канал и код приглашения")
def create_canal(data: CanalCreate, db: DbSession) -> CanalRead:
    return canal_service.create_canal(db, data)


@router.get("/canals/{canal_id}/supply", response_model=list[SupplyRead],
            summary="Подача воды по декадам")
def get_supply(
    canal_id: UUID,
    db: DbSession,
    season: Annotated[int, Query(ge=2000, le=2200)],
) -> list[SupplyRead]:
    return canal_service.list_supply(db, canal_id, season)


@router.put(
    "/canals/{canal_id}/supply",
    response_model=list[SupplyRead],
    summary="Ввести или обновить подачу воды по декадам",
)
@router.post(
    "/canals/{canal_id}/supply",
    response_model=list[SupplyRead],
    include_in_schema=False,
)
def put_supply(canal_id: UUID, data: SupplyScheduleInput, db: DbSession) -> list[SupplyRead]:
    return canal_service.save_supply(db, canal_id, data)


@router.get("/canals/{canal_id}/demand", summary="Спрос и подача по декадам")
def get_demand(
    canal_id: UUID,
    db: DbSession,
    season: Annotated[int, Query(ge=2000, le=2200)],
) -> dict:
    return canal_service.get_latest_demand(db, canal_id, season)


@router.get(
    "/canals/{canal_id}/farms",
    response_model=list[CanalFarmMapItem],
    summary="Хозяйства, поля и культуры канала",
)
def get_canal_farms(
    canal_id: UUID,
    db: DbSession,
    season: Annotated[int, Query(ge=2000, le=2200)],
) -> list[CanalFarmMapItem]:
    return canal_service.list_canal_farms(db, canal_id, season)


@router.post(
    "/canals/{canal_id}/coordinate",
    response_model=CanalPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Сформировать план канала и предложения хозяйствам",
)
@router.post(
    "/canals/{canal_id}/plans:coordinate",
    response_model=CanalPlanRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def coordinate_plan(canal_id: UUID, data: CoordinatePlanInput, db: DbSession) -> CanalPlanRead:
    return canal_service.coordinate_plan(db, canal_id, data)


@router.get(
    "/canal-plans/{plan_id}", response_model=CanalPlanRead, summary="Получить план канала"
)
def get_plan(plan_id: UUID, db: DbSession) -> CanalPlanRead:
    return canal_service.get_plan(db, plan_id)


@router.post(
    "/canal-proposals/{proposal_id}:respond", summary="Ответить на предложение канала"
)
def respond_to_proposal(
    proposal_id: UUID,
    data: ProposalResponseInput,
    db: DbSession,
    response: Response,
) -> dict:
    response.status_code = status.HTTP_200_OK
    return canal_service.respond_to_proposal(db, proposal_id, data.response, data.counter_note)
