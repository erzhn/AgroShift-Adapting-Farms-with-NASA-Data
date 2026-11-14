import pytest

from agroshift_core.canal import CanalInputError, FarmDemand, ShiftOption, coordinate_canal


def test_greedy_shift_reduces_peak_and_keeps_zero_sum_compensation():
    farms = [
        FarmDemand(
            "farm-a",
            (100.0, 0.0),
            100.0,
            1_000.0,
            10.0,
            (ShiftOption(-10, (0.0, 100.0), 500.0),),
        ),
        FarmDemand("farm-b", (100.0, 0.0), 100.0, 1_000.0, 10.0),
    ]

    result = coordinate_canal(farms, (120.0, 100.0))

    assert result.demand_before_m3_by_decade == (200.0, 0.0)
    assert result.demand_after_m3_by_decade == (100.0, 100.0)
    assert result.deficit_after_m3_by_decade == (0.0, 0.0)
    assert result.farmers[0].selected_shift_days == -10
    assert result.farmers[0].coordinated_income_som >= result.farmers[0].baseline_income_som
    assert sum(farm.compensation_som for farm in result.farmers) == pytest.approx(0.0)
    assert result.coordination_useful


def test_water_rights_define_proportional_baseline_allocation():
    farms = [
        FarmDemand("large-right", (100.0,), 3.0, 1_000.0, 10.0),
        FarmDemand("small-right", (100.0,), 1.0, 1_000.0, 10.0),
    ]

    result = coordinate_canal(farms, (80.0,))

    assert [farm.assigned_water_m3_by_decade for farm in result.farmers] == [
        (60.0,),
        (20.0,),
    ]
    assert [farm.baseline_income_som for farm in result.farmers] == [600.0, 200.0]


def test_no_shift_is_selected_when_it_does_not_reduce_total_deficit():
    farms = [
        FarmDemand("farm-a", (100.0, 0.0), 1.0, 1_000.0, 1.0,
                   (ShiftOption(10, (100.0, 40.0), 10.0),)),
    ]

    result = coordinate_canal(farms, (50.0, 0.0))

    assert result.farmers[0].selected_shift_days == 0
    assert result.deficit_after_m3_by_decade == (50.0, 0.0)
    assert not result.coordination_useful


def test_plan_is_not_applied_when_compensation_cannot_protect_every_farm():
    farms = [
        FarmDemand(
            "farm-a",
            (100.0, 0.0),
            100.0,
            1_000.0,
            10.0,
            (ShiftOption(-10, (0.0, 100.0), 1_000.0),),
        ),
    ]

    result = coordinate_canal(farms, (50.0, 100.0))

    assert result.farmers[0].selected_shift_days == 0
    assert result.deficit_after_m3_by_decade == result.deficit_before_m3_by_decade
    assert not result.fairness_feasible


@pytest.mark.parametrize(
    ("farms", "supply"),
    [
        ([], (10.0,)),
        ([FarmDemand("farm-a", (1.0,), 1.0, 1.0, 0.0)], (-1.0,)),
        ([FarmDemand("farm-a", (float("nan"),), 1.0, 1.0, 0.0)], (1.0,)),
        ([FarmDemand("farm-a", (1.0,), 1.0, 1.0, 0.0),
          FarmDemand("farm-a", (1.0,), 1.0, 1.0, 0.0)], (1.0,)),
        ([FarmDemand("farm-a", (1.0,), 1.0, 1.0, 0.0,
                     (ShiftOption(30, (1.0,), 0.0),))], (1.0,)),
    ],
)
def test_invalid_coordination_inputs_are_rejected(farms, supply):
    with pytest.raises(CanalInputError):
        coordinate_canal(farms, supply)
