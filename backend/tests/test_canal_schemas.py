from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import ProposalResponse
from app.schemas.canal import (
    CanalCreate,
    CoordinatePlanInput,
    FarmDemandSimulation,
    ProposalResponseInput,
    ShiftSimulation,
    SupplyPoint,
    SupplyScheduleInput,
)


def test_canal_create_requires_valid_geojson_and_efficiency():
    payload = {
        "name": "Demo canal",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [[[74.5, 42.8], [74.6, 42.9]]],
        },
        "snow_catchment_geometry": {
            "type": "MultiPolygon",
            "coordinates": [[[[74.5, 42.8], [74.6, 42.8], [74.6, 42.9],
                              [74.5, 42.9], [74.5, 42.8]]]],
        },
        "conveyance_efficiency": 0.5,
    }

    assert CanalCreate.model_validate(payload).name == "Demo canal"
    payload["conveyance_efficiency"] = 0.9
    with pytest.raises(ValidationError):
        CanalCreate.model_validate(payload)


def test_supply_schedule_rejects_duplicate_decades():
    data = {
        "season": 2027,
        "decades": [
            {"decade": 1, "volume_m3": 1000},
            {"decade": 1, "volume_m3": 500},
        ],
    }

    with pytest.raises(ValidationError):
        SupplyScheduleInput.model_validate(data)
    assert SupplyPoint(decade=36, volume_m3=0).decade == 36


def test_coordination_payload_requires_36_decades_and_snapshot_provenance():
    demand = [0.0] * 36
    input_data = CoordinatePlanInput(
        season=2027,
        water_model_version="0.1.0",
        snapshot_ids=["power-demo-v1"],
        simulations=[
            FarmDemandSimulation(
                farm_id=uuid4(),
                sowing_date=date(2027, 4, 1),
                demand_m3_by_decade=demand,
                crop_demand_m3_by_decade={"demo_maize": demand},
                expected_income_som=100_000,
                income_loss_per_m3=2.0,
            )
        ],
    )

    assert len(input_data.simulations[0].demand_m3_by_decade) == 36
    with pytest.raises(ValidationError):
        ShiftSimulation(
            shift_days=10,
            demand_m3_by_decade=[0.0],
            crop_demand_m3_by_decade={"demo_maize": [0.0]},
            income_loss_som=0,
        )
    bad_crop_total = demand.copy()
    bad_crop_total[0] = 1.0
    with pytest.raises(ValidationError):
        FarmDemandSimulation(
            farm_id=uuid4(),
            sowing_date=date(2027, 4, 1),
            demand_m3_by_decade=demand,
            crop_demand_m3_by_decade={"demo_maize": bad_crop_total},
            expected_income_som=100_000,
            income_loss_per_m3=2.0,
        )


def test_coordination_request_can_use_server_side_water_simulations():
    assert CoordinatePlanInput.model_validate({"season": 2027}).simulations is None


def test_counter_proposal_requires_explanation_and_pending_is_not_a_response():
    with pytest.raises(ValidationError):
        ProposalResponseInput(response=ProposalResponse.COUNTER)
    with pytest.raises(ValidationError):
        ProposalResponseInput(response=ProposalResponse.PENDING)
    assert ProposalResponseInput(response=ProposalResponse.AGREE).response == ProposalResponse.AGREE
