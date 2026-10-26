# UEV Architecture and modelling integrity

## System layers
- **Explore:** map and GIS inputs (planned PostGIS/MapLibre).
- **Model:** independent Python package (`src/uev`).
- **Results:** quantitative scenarios and eventual station/route maps.
- **Storage:** versioned, sourced and confidence-tagged mobility and energy records (planned).

## Modelling modes
1. Cost any user-defined deployment option.
2. Compare charging technology packages.
3. Later: optimize least system cost with grid/transport constraints.
4. Later: fastest achievable electrification, universal coverage, renewables, resilience and annual budget limits.

## Priority data
Active ICE and EV stock; trips and vehicle-km; charging/swapping operators; distribution feeder and transformer capacities; energy load curves; candidate-site land, transport networks and technology lifetimes/costs.

## Scientific boundaries
Current CAPEX = number of illustrative charger units x installed cost, plus optional grid-upgrade proxy. It is NOT total transition cost or an optimized national plan. Annual energy assumes 365 operating days. The peak fraction is NOT load-flow. Before policy use, integrate measured time-series energy use, fleet turnover, district allocation and uncertainty bounds.

## Next milestone
Georeferenced fleet and charging inventory, station suitability and location-allocation with spatial candidate-site data.
