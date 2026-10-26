# Phase 3: Charging station location-allocation
Models least-cost candidate-site CAPEX for a given energy service coverage target, maximum served energy under a capital budget, and fixed user-selected station portfolios. Uses SciPy HiGHS MILP with binary station decisions, continuous kWh/day allocations, candidate capacities, and a straight-line service radius. Access GET /api/v1/location/optimize or /docs.

**Scientific limitations:** All example costs, vehicle demand, coordinates, and grid indicators are synthetic. Distances are great-circle rather than route-network distances; grid availability is unverified. Station CAPEX omits land, energy, vehicles, OPEX, maintenance and network upgrade investment. Results are NOT full national least-cost transition estimates or approved charging sites.

Next: calibrated road travel times, verified hourly mobility/grid data, multiple vehicle types and technology-specific equipment, actual network capacity and multi-year lifecycle investment scenarios.
