"""UEV Phase 3 capacitated candidate-site optimization (demonstration inputs only).

Demand may be split across stations; distances are straight-line proxies, not roads.
Site CAPEX is not a grid-certified or full transport transition cost.
"""
from dataclasses import dataclass
from math import radians, sin, cos, asin, sqrt, isfinite
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix
import numpy as np

@dataclass(frozen=True)
class Demand:
    id: str
    name: str
    lon: float
    lat: float
    kwh_day: float

@dataclass(frozen=True)
class Site:
    id: str
    name: str
    lon: float
    lat: float
    capacity_kwh_day: float
    capex_usd: float
    eligible: bool = True

def km(a, b):
    x, y = radians(b.lat-a.lat), radians(b.lon-a.lon)
    z = sin(x/2)**2 + cos(radians(a.lat))*cos(radians(b.lat))*sin(y/2)**2
    return 12742.0176 * asin(min(1, sqrt(z)))

def optimize(demand: list[Demand], sites: list[Site], *, mode: str="least_cost",
             coverage_pct: float=100, radius_km: float=25,
             budget_usd: float|None=None, selected_site_ids: list[str]|None=None) -> dict:
    """Solve binary facility opening + continuous kWh/day allocation with HiGHS.

    Modes: least_cost (meet coverage as cheaply as possible), max_coverage
    (maximize served energy under budget), manual (cost fixed user site set).
    """
    if mode not in ("least_cost", "max_coverage", "manual"):
        raise ValueError("Unsupported mode")
    if not 0<=coverage_pct<=100 or not isfinite(radius_km) or radius_km<=0:
        raise ValueError("Invalid coverage or service radius")
    if budget_usd is not None and (not isfinite(budget_usd) or budget_usd<0):
        raise ValueError("Invalid budget")
    if mode=="max_coverage" and budget_usd is None:
        raise ValueError("Maximum coverage requires an investment budget")
    if len({d.id for d in demand})!=len(demand) or len({s.id for s in sites})!=len(sites):
        raise ValueError("Duplicate identifiers")
    for d in demand:
        if not all(isfinite(v) for v in (d.lon,d.lat,d.kwh_day)) or d.kwh_day<0 or abs(d.lon)>180 or abs(d.lat)>90:
            raise ValueError("Invalid demand inputs")
    for s in sites:
        if not all(isfinite(v) for v in (s.lon,s.lat,s.capacity_kwh_day,s.capex_usd)) or s.capacity_kwh_day<=0 or s.capex_usd<0 or abs(s.lon)>180 or abs(s.lat)>90:
            raise ValueError("Invalid site inputs")
    allowed = [s for s in sites if s.eligible]
    selected = set(selected_site_ids or [])
    if mode=="manual" and (not selected or selected-({s.id for s in allowed})):
        raise ValueError("Manual mode requires known eligible sites")
    if mode!="manual" and selected_site_ids:
        raise ValueError("Manual selection only allowed in manual mode")
    active = [d for d in demand if d.kwh_day>0]
    total=sum(d.kwh_day for d in active)
    common={"mode":mode,"total_demand_kwh_day":round(total,3),"cost_scope":"candidate_site_capex_only",
            "distance_method":"straight_line_not_road_distance","data_status":"synthetic_demonstration"}
    if total==0:
        return {**common,"status":"optimal","served_kwh_day":0,"coverage_pct":100,"selected_sites":[],"assignments":[],"site_capex_usd":0}
    if not allowed:
        return {**common,"status":"infeasible","reason":"No eligible sites"}
    n,m=len(active),len(allowed)
    arcs=[(i,j,km(d,s)) for i,d in enumerate(active) for j,s in enumerate(allowed) if km(d,s)<=radius_km]
    k=len(arcs); size=m+k+n
    cost=np.zeros(size); integ=np.zeros(size); integ[:m]=1
    lo=np.zeros(size); hi=np.full(size,np.inf); hi[:m]=1
    for i,d in enumerate(active):hi[m+k+i]=d.kwh_day
    for j,s in enumerate(allowed):
        cost[j] = s.capex_usd if mode=="least_cost" else (s.capex_usd*1e-10 if mode=="max_coverage" else 0)
        if mode=="manual":lo[j]=hi[j]=int(s.id in selected)
    if mode=="max_coverage":cost[m+k:]=1
    rows=[]
    for i,d in enumerate(active):
        row={m+p:1 for p,(ii,j,dist) in enumerate(arcs) if ii==i}
        row[m+k+i]=1;rows.append((row,d.kwh_day,d.kwh_day))
    for j,s in enumerate(allowed):
        row={j:-s.capacity_kwh_day}
        row.update({m+p:1 for p,(i,jj,dist) in enumerate(arcs) if jj==j})
        rows.append((row,-np.inf,0))
    if mode!="max_coverage":rows.append(({m+k+i:1 for i in range(n)},-np.inf,total*(1-coverage_pct/100)+1e-7))
    if budget_usd is not None:rows.append(({j:s.capex_usd for j,s in enumerate(allowed)},-np.inf,budget_usd))
    mat=lil_matrix((len(rows),size),dtype=float);low=[];high=[]
    for r,(vals,a,b) in enumerate(rows):
        for col,value in vals.items():mat[r,col]=value
        low.append(a);high.append(b)
    result=milp(c=cost,integrality=integ,bounds=Bounds(lo,hi),
                constraints=LinearConstraint(mat.tocsr(),low,high),
                options={"time_limit":30,"mip_rel_gap":1e-8})
    if result.x is None or result.status!=0:
        return {**common,"status":"infeasible" if result.status==2 else "solver_error",
                "reason":"Coverage, distance, capacity or budget constraints cannot be satisfied" if result.status==2 else "Solver did not prove optimality"}
    x=result.x
    opened=[{"id":s.id,"name":s.name,"lon":s.lon,"lat":s.lat,
             "capacity_kwh_day":s.capacity_kwh_day,"capex_usd":s.capex_usd,
             "allocated_kwh_day":round(sum(max(0,x[m+p]) for p,(i,jj,dist) in enumerate(arcs) if jj==j),3)}
            for j,s in enumerate(allowed) if x[j]>.5]
    assignments=[{"demand_id":active[i].id,"site_id":allowed[j].id,
                  "kwh_day":round(float(x[m+p]),3),"distance_km":round(dist,3),
                  "from":[active[i].lon,active[i].lat],"to":[allowed[j].lon,allowed[j].lat]}
                 for p,(i,j,dist) in enumerate(arcs) if x[m+p]>1e-5]
    served=total-sum(max(0,float(x[m+k+i])) for i in range(n))
    return {**common,"status":"optimal","coverage_pct":round(100*served/total,3),
            "served_kwh_day":round(served,3),"unserved_kwh_day":round(total-served,3),
            "site_capex_usd":round(sum(s["capex_usd"] for s in opened),2),
            "selected_sites":opened,"assignments":assignments,
            "warning":"Not validated road routing, grid capacity, charging queues or national least-cost transition."}

def as_geojson(result: dict) -> dict:
    features=[]
    for s in result.get("selected_sites",[]):
        features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[s["lon"],s["lat"]]},
                         "properties":{"kind":"selected_station","site_id":s["id"],"capex_usd":s["capex_usd"]}})
    for a in result.get("assignments",[]):
        features.append({"type":"Feature","geometry":{"type":"LineString","coordinates":[a["from"],a["to"]]},
                         "properties":{"kind":"indicative_assignment","site_id":a["site_id"]}})
    return {"type":"FeatureCollection","features":features}
