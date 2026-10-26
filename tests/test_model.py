import pytest
from uev import Fleet, Charger, project, compare_technologies

FLEETS = [Fleet("Motorcycles", 1000, 100, 80, 0.05)]
AC = Charger("AC", 10, 10, 0.5, 3000)
DC = Charger("DC", 50, 10, 0.5, 12000)

def test_zero_target_retains_existing_evs():
    result = project(FLEETS, 2026, 2026, 0, AC)
    assert result["future_evs"] == 100

def test_full_target():
    result = project(FLEETS, 2026, 2030, 1, AC)
    assert result["future_evs"] == 1000
    assert result["new_evs"] == 900

def test_energy_conversion_and_charger_count():
    result = project(FLEETS, 2026, 2026, 1, AC)
    assert result["grid_kwh_per_day"] == pytest.approx(4444.44, abs=0.01)
    assert result["number_of_chargers"] == 89

def test_no_future_horizon_before_baseline():
    with pytest.raises(ValueError):
        project(FLEETS, 2026, 2025, 1, AC)

def test_invalid_fleet_rejected():
    with pytest.raises(ValueError):
        project([Fleet("invalid", 10, 11, 20, 0.03)], 2026, 2030, 1, AC)

def test_multiple_options_and_best_cost():
    comparison = compare_technologies(FLEETS, 2026, 2030, 1, [AC, DC])
    costs = {r["charger_technology"]: r["infrastructure_capex_proxy"] for r in comparison["all_options"]}
    assert costs[comparison["lowest_charger_capex_option"]] == min(costs.values())
