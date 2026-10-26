"""Transparent, deterministic prototype for fleet electrification and charging costs.

All distances and costs are scenario inputs, not Uganda observations.
This module does not claim to model feeder power flow or geographic station suitability.
"""
from dataclasses import dataclass, asdict
from math import ceil

@dataclass(frozen=True)
class Fleet:
    name: str
    total_vehicles: int
    electric_vehicles: int
    km_per_day: float
    kwh_per_km: float
    growth_rate: float = 0.0

    def validate(self):
        if self.total_vehicles < 0 or not 0 <= self.electric_vehicles <= self.total_vehicles:
            raise ValueError("Electric fleet must be between zero and total vehicle fleet")
        if self.km_per_day < 0 or self.kwh_per_km < 0 or self.growth_rate < -1:
            raise ValueError("Negative activity or invalid fleet growth")

@dataclass(frozen=True)
class Charger:
    name: str
    rated_kw: float
    usable_hours_per_day: float
    utilization: float
    installed_cost: float
    efficiency: float = 0.9

    def validate(self):
        if self.rated_kw <= 0 or self.usable_hours_per_day <= 0 or self.installed_cost < 0:
            raise ValueError("Invalid charger capacity, hours or cost")
        if not 0 < self.utilization <= 1 or not 0 < self.efficiency <= 1:
            raise ValueError("Utilization and efficiency must be in (0,1]")

def project(fleets: list[Fleet], baseline_year: int, target_year: int,
            electrification_target: float, charger: Charger,
            coincident_peak_fraction: float = 0.20,
            grid_upgrade_cost_per_kw: float = 0.0) -> dict:
    """Calculate demand and a simple infrastructure costing for one scenario.

    Installed charging capacity is sized using effective DAILY throughput.
    Coincident peak is a proxy only, not a feeder-level simulation.
    Grid upgrades are an optional scenario cost, not a calibrated prediction.
    """
    if not baseline_year <= target_year <= 2200:
        raise ValueError("Target year must be between baseline year and 2200")
    if not 0 <= electrification_target <= 1:
        raise ValueError("Electrification target must be in [0,1]")
    if not 0 <= coincident_peak_fraction <= 1 or grid_upgrade_cost_per_kw < 0:
        raise ValueError("Invalid peak fraction or upgrade cost")
    charger.validate()
    elapsed = target_year - baseline_year
    breakdown = []
    total_battery_kwh_day = 0.0
    total_conversions = 0
    total_evs = 0
    for fleet in fleets:
        fleet.validate()
        future_total = round(fleet.total_vehicles * (1 + fleet.growth_rate) ** elapsed)
        future_evs = max(min(future_total, ceil(future_total * electrification_target)),
                         min(future_total, fleet.electric_vehicles))
        conversions = max(future_evs - fleet.electric_vehicles, 0)
        battery_kwh_day = future_evs * fleet.km_per_day * fleet.kwh_per_km
        total_battery_kwh_day += battery_kwh_day
        total_conversions += conversions
        total_evs += future_evs
        breakdown.append({"vehicle_type": fleet.name, "future_fleet": future_total,
                          "future_evs": future_evs, "new_evs": conversions,
                          "battery_kwh_per_day": round(battery_kwh_day, 2)})
    grid_kwh_day = total_battery_kwh_day / charger.efficiency
    energy_per_charger_day = charger.rated_kw * charger.usable_hours_per_day * charger.utilization
    charger_count = ceil(grid_kwh_day / energy_per_charger_day) if grid_kwh_day else 0
    installed_kw = charger_count * charger.rated_kw
    peak_kw_proxy = installed_kw * coincident_peak_fraction
    hardware_cost = charger_count * charger.installed_cost
    grid_cost = peak_kw_proxy * grid_upgrade_cost_per_kw
    return {"baseline_year": baseline_year, "target_year": target_year,
            "target_fraction": electrification_target, "vehicle_breakdown": breakdown,
            "future_evs": total_evs, "new_evs": total_conversions,
            "grid_kwh_per_day": round(grid_kwh_day, 2),
            "grid_mwh_per_year": round(grid_kwh_day * 365 / 1000, 2),
            "number_of_chargers": charger_count, "charger_installed_kw": installed_kw,
            "peak_kw_proxy": round(peak_kw_proxy, 2),
            "charger_capex": round(hardware_cost, 2), "grid_upgrade_proxy": round(grid_cost, 2),
            "infrastructure_capex_proxy": round(hardware_cost + grid_cost, 2),
            "charger_technology": charger.name,
            "limitations": "Synthetic input model; excludes vehicles, OPEX, replacement, land, feeder studies and station geography."}

def compare_technologies(fleets: list[Fleet], baseline_year: int,
                         target_year: int, electrification_target: float,
                         options: list[Charger]) -> dict:
    """Compare costed technology alternatives; lowest CAPEX is a limited proxy only."""
    if not options:
        raise ValueError("At least one charging technology is required")
    results = [project(fleets, baseline_year, target_year, electrification_target, c)
               for c in options]
    cheapest = min(results, key=lambda row: row["infrastructure_capex_proxy"])
    return {"all_options": results, "lowest_charger_capex_option": cheapest["charger_technology"],
            "note": "Not a national least-cost transition or full lifecycle cost optimization."}
