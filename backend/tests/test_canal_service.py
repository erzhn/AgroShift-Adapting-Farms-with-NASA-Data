from types import SimpleNamespace

from app.services.canal import _series_by_decade


def test_canal_uses_farm_intake_gross_demand_before_efficiency_conversion():
    field_season = SimpleNamespace(
        decades=[
            SimpleNamespace(decade=1, need_gross_m3=100.0, need_head_m3=200.0),
            SimpleNamespace(decade=3, need_gross_m3=25.0, need_head_m3=50.0),
        ]
    )

    series = _series_by_decade(field_season)

    assert len(series) == 36
    assert series[0] == 100.0
    assert series[1] == 0.0
    assert series[2] == 25.0
    assert sum(series) == sum(item.need_gross_m3 for item in field_season.decades)
