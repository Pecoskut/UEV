"""UEV demonstration UI. All figures are synthetic and for functionality testing only."""
import streamlit as st
from uev import Fleet, Charger, project, compare_technologies

st.set_page_config(page_title="UEV | Planning Prototype", layout="wide")
st.title("UEV | E-Mobility Energy Planning")
st.warning("DEMONSTRATION ONLY: Synthetic numbers, not verified data for Uganda.")
st.caption("Prototype: scenario energy demand, chargers and indicative infrastructure capital costs.")
baseline = 2026
year = st.number_input("Planning year", min_value=baseline, max_value=2200, value=2040, step=1)
target = st.slider("Electric fleet target (%)", 0, 100, 100)
technology = st.selectbox("Charging infrastructure option", ["AC charging", "DC charging", "Battery swapping"])
fleet_n = st.number_input("Illustrative motorcycle fleet", min_value=0, value=10000, step=500)
daily_km = st.number_input("Distance per motorcycle (km/day)", min_value=0, value=70, step=5)
fleets = [Fleet("Motorcycles", int(fleet_n), 250, float(daily_km), 0.045, 0.02)]
chargers = {
    "AC charging": Charger("AC charging", 7, 10, 0.55, 2500),
    "DC charging": Charger("DC charging", 60, 12, 0.55, 36000),
    "Battery swapping": Charger("Battery swapping", 24, 18, 0.70, 18000),
}
results = project(fleets, baseline, int(year), target/100, chargers[technology])
a,b,c,d = st.columns(4)
a.metric("Projected electric vehicles", f'{results["future_evs"]:,}')
b.metric("Annual grid energy (MWh)", f'{results["grid_mwh_per_year"]:,.0f}')
c.metric("Illustrative charging units", f'{results["number_of_chargers"]:,}')
d.metric("Infrastructure CAPEX proxy (USD)", f'${results["infrastructure_capex_proxy"]:,.0f}')
st.subheader("Costed infrastructure alternatives")
comparison = compare_technologies(fleets, baseline, int(year), target/100, list(chargers.values()))
st.dataframe([{"Technology": r["charger_technology"], "Units": r["number_of_chargers"],
               "Capacity kW": r["charger_installed_kw"], "Indicative CAPEX USD": r["infrastructure_capex_proxy"]}
              for r in comparison["all_options"]], use_container_width=True)
st.info("This is a simplified engineering demonstration. Site suitability, vehicle purchase costs, grid studies, OPEX and actual Uganda datasets are future development phases.")
