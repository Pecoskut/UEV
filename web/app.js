"use strict";
const LAYERS = ["charging", "candidates", "grid", "mobility"];
const COLORS = {charging:"#f09a2b", candidates:"#00877e", grid:"#9c68e8", mobility:"#338ee0"};
const mapCache = {};
let map = null;
let planOverlay = {type:"FeatureCollection",features:[]};
let lastPlan = null;
const $ = id => document.getElementById(id);
const nice = n => Number(n).toLocaleString("en-US", {maximumFractionDigits: 1});

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    let reason = `Request failed (${response.status})`;
    try { reason = (await response.json()).detail || reason; } catch (_ignored) {}
    throw new Error(reason);
  }
  return response.json();
}
function query(params) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k,v]) => {if (v !== "" && v !== null && v !== undefined) p.set(k, String(v));});
  return p.toString();
}
function selected() {
  return {district: $("district").value, lens: $("lens").value};
}
function setStatus(message) { $("model-status").textContent = message; }
function node(tag, cls, text) {
  const element = document.createElement(tag);
  if (cls) element.className = cls;
  if (text !== undefined) element.textContent = String(text);
  return element;
}
function popupContent(feature) {
  const p = feature.properties;
  const content = node("div", "");
  content.append(node("div", "popup-title", p.name || "Demonstration asset"));
  [ ["District",p.district], ["Layer",p.layer], ["Score",p.suitability_score === null ? "Excluded" : p.suitability_score], ["Status", "Synthetic / not verified"]]
    .filter(([,v]) => v !== undefined).forEach(([k,v]) => {
      const row = node("div","popup-field"); row.append(node("b", "", k + ": ")); row.append(document.createTextNode(String(v)));content.append(row);
    });
  return content;
}
function mapStyle() {
  return {version:8, sources:{osm:{type:"raster",tiles:["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],tileSize:256,attribution:"© OpenStreetMap contributors"}},layers:[{id:"osm-base",type:"raster",source:"osm"}]};
}
function initMap() {
  if (!window.maplibregl) {
    $("map").innerHTML="";$("map").append(node("div","error","MapLibre could not be loaded. Check internet access. The modelling API remains available.")); return;
  }
  map = new maplibregl.Map({container:"map",style:mapStyle(),center:[32.78,0.75],zoom:7.2,maxZoom:16});
  map.addControl(new maplibregl.NavigationControl({showCompass:false}),"bottom-right");
  map.on("load", () => {
    $("map").querySelector(".map-loading")?.remove();
    LAYERS.forEach(layer => {
      map.addSource("data-"+layer,{type:"geojson",data:{type:"FeatureCollection",features:[]}});
      map.addLayer({id:"points-"+layer,type:"circle",source:"data-"+layer,paint:{
        "circle-radius":layer === "candidates"?9:7,
        "circle-color":COLORS[layer],"circle-stroke-width":2,"circle-stroke-color":"#ffffff","circle-opacity":0.90
      }});
      map.on("click","points-"+layer,e => {
        if (!e.features?.length) return;
        new maplibregl.Popup({maxWidth:"300px"}).setLngLat(e.lngLat).setDOMContent(popupContent(e.features[0])).addTo(map);
      });
      map.on("mouseenter","points-"+layer,()=>{map.getCanvas().style.cursor="pointer";});
      map.on("mouseleave","points-"+layer,()=>{map.getCanvas().style.cursor="";});
    });
    applyMapLayers();
    map.addSource("uev-plan",{type:"geojson",data:planOverlay});
    map.addLayer({id:"uev-plan-links",type:"line",source:"uev-plan",
      filter:["==",["get","kind"],"indicative_assignment"],
      paint:{"line-color":"#0a807c","line-width":2.5,"line-opacity":0.6,"line-dasharray":[2,2]}});
    map.addLayer({id:"uev-plan-stations",type:"circle",source:"uev-plan",
      filter:["==",["get","kind"],"selected_station"],
      paint:{"circle-color":"#eb820d","circle-stroke-color":"#133843",
             "circle-stroke-width":2.5,"circle-radius":12}});
    map.on("click","uev-plan-stations",e=>{
      if(!e.features?.length) return;
      const p=e.features[0].properties;
      const content=node("div","");
      content.append(node("strong","",p.site_id+" • selected demonstration site"));
      content.append(node("p","", "Illustrative site CAPEX: $"+nice(p.capex_usd)));
      new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(content).addTo(map);
    });
  });
}
function applyMapLayers() {
  if (!map || !map.isStyleLoaded()) return;
  LAYERS.forEach(layer => {
    const featureCollection = mapCache[layer] || {type:"FeatureCollection",features:[]};
    const source = map.getSource("data-"+layer);
    if (source) source.setData(featureCollection);
    const toggle = document.querySelector(`[data-layer="${layer}"]`);
    if (map.getLayer("points-"+layer)) map.setLayoutProperty("points-"+layer,"visibility",(toggle ? toggle.checked : true)?"visible":"none");
  });
}
function updatePlanLayer(fc) {
  planOverlay=fc || {type:"FeatureCollection",features:[]};
  if(map?.getSource("uev-plan")) map.getSource("uev-plan").setData(planOverlay);
}
function focusLocation(lon,lat) {
  if (map) map.flyTo({center:[lon,lat],zoom:12,essential:true});
}
async function reload() {
  const area = selected();
  updatePlanLayer(null);
  lastPlan=null;
  $("download-plan").disabled=true;
  $("model-status").textContent="RUN MODEL TO UPDATE";
  $("map-area-title").textContent=(area.district || "Demo geography")+" · Uganda";
  try {
    const [summary, sites, ...collections] = await Promise.all([
      api("/api/v1/summary?"+query({district:area.district})),
      api("/api/v1/sites/ranked?"+query(area)),
      ...LAYERS.map(layer=>api("/api/v1/layers/"+layer+"?"+query(area)))
    ]);
    $("metric-fleet").textContent=nice(summary.total_vehicles);
    $("metric-electric").textContent=nice(summary.electric_vehicles);
    $("metric-share").textContent=nice(summary.electric_share_pct)+"%";
    $("metric-sites").textContent=nice(sites.length);
    LAYERS.forEach((layer,index)=>{mapCache[layer]=collections[index];});
    applyMapLayers();
    const chooser=$("manual-sites");chooser.replaceChildren();
    sites.forEach(s=>{
      const option=document.createElement("option");
      option.value=s.id;option.textContent=s.name+" • "+s.district;
      chooser.append(option);
    });
    const list=$("site-list");list.replaceChildren();
    if(!sites.length) list.append(node("div","empty","No eligible demonstration candidate sites in this district."));
    sites.slice(0,8).forEach((s,i)=>{
      const btn=node("button","site"); btn.type="button";
      btn.append(node("span","site-rank",i+1));
      const main=node("span","site-main");main.append(node("strong","",s.name));main.append(node("small","",s.district));btn.append(main);
      const score=node("span","score",s.suitability_score);score.append(node("small","","/ 100"));btn.append(score);
      btn.addEventListener("click",()=>focusLocation(s.longitude,s.latitude));list.append(btn);
    });
    if(map && map.isStyleLoaded() && area.district) {
      const coords=collections.flatMap(collection=>collection.features.map(f=>f.geometry.coordinates));
      if (coords.length) {
        const bounds=coords.reduce((b,p)=>b.extend(p),new maplibregl.LngLatBounds(coords[0],coords[0]));
        map.fitBounds(bounds,{padding:70,maxZoom:11,duration:700});
      }
    } else if(map && map.isStyleLoaded()) map.flyTo({center:[32.78,0.85],zoom:7.2,duration:700});
    setStatus("READY TO RUN");
  } catch(error) {$("site-list").replaceChildren(node("div","error",error.message));setStatus("DATA ERROR");}
}
function updateScenarioControls() {
  const mode=$("plan-mode").value;
  $("budget-wrap").hidden=mode!=="max_coverage";
  $("manual-wrap").hidden=mode!=="manual";
  $("coverage-wrap").hidden=mode==="max_coverage";
}
function drawScenario(data) {
  const loc=data.location, fleet=data.fleet;
  $("r-ev").textContent=nice(fleet.future_evs);
  $("r-energy").textContent=nice(fleet.grid_mwh_per_year)+" MWh";
  $("r-chargers").textContent=loc.status==="optimal"?nice(loc.selected_sites.length):"—";
  $("r-cost").textContent=loc.status==="optimal"?"$"+nice(loc.site_capex_usd):"Not feasible";
  $("r-coverage").textContent=loc.status==="optimal"?nice(loc.coverage_pct)+"%":"—";
  $("r-equip").textContent="$"+nice(fleet.charger_capex);
  const warnings=$("plan-message");
  warnings.replaceChildren();
  warnings.append(node("strong","",loc.status==="optimal"?"Demonstration scenario solved":"Scenario not fully feasible"));
  warnings.append(node("p","",loc.reason || data.cost_note));
  if(loc.status!=="optimal")warnings.append(node("p","", "Demand remains forecast, but station selection cannot meet the configured constraints. Try greater site capacity, a wider radius or a lower coverage target."));
  const sites=$("plan-sites");sites.replaceChildren();
  for(const s of loc.selected_sites || []){
    const b=node("button","site");b.type="button";
    b.append(node("strong","",s.name));
    b.append(node("small","", "  $"+nice(s.capex_usd)+" • "+nice(s.allocated_kwh_day)+" kWh/day"));
    b.addEventListener("click",()=>focusLocation(s.lon,s.lat));
    sites.append(b);
  }
  if(!loc.selected_sites?.length)sites.append(node("div","empty","No funded stations were selected for this scenario."));
  const rows=$("plan-trajectory");rows.replaceChildren();
  const series=data.trajectory || [];
  const preview=series.length>12?[...series.slice(0,5),...series.slice(-7)]:series;
  preview.forEach(entry=>{
    const tr=document.createElement("tr");
    [entry.year,nice(entry.electric_vehicles),nice(entry.grid_mwh_per_year)].forEach(v=>tr.append(node("td","",v)));
    rows.append(tr);
  });
  updatePlanLayer(loc.geojson);
  setStatus(loc.status==="optimal"?"SCENARIO SOLVED":"NOT FEASIBLE / INCOMPLETE");
}
async function runModel() {
  const year=Number($("year").value),pct=Number($("target").value);
  const coverage=Number($("energy-coverage").value);
  const radius=Number($("service-radius").value);
  const modules=Number($("modules-site").value);
  const mode=$("plan-mode").value;
  const budget=mode==="max_coverage"?Number($("plan-budget").value):null;
  const sites=mode==="manual"?Array.from($("manual-sites").selectedOptions).map(o=>o.value):[];
  if(!Number.isInteger(year)||year<2026||year>2200||!Number.isFinite(pct)||pct<0||pct>100||
     !Number.isFinite(coverage)||coverage<0||coverage>100||
     !Number.isFinite(radius)||radius<=0||!Number.isInteger(modules)||modules<1||modules>100||
     (mode==="max_coverage"&&(!Number.isFinite(budget)||budget<0))||
     (mode==="manual"&&!sites.length)){
    setStatus("INVALID CONFIGURATION");return;
  }
  setStatus("CALCULATING…");
  $("run-model").disabled=true;
  $("download-plan").disabled=true;
  try {
    const data=await api("/api/v1/plans/run?"+query({
      district:$("district").value,target_year:year,target_pct:pct,
      technology:$("technology").value,mode,
      energy_coverage_pct:coverage,radius_km:radius,
      modules_per_site:modules,budget_usd:budget,selected_site_ids:sites.join(",")
    }));
    lastPlan=data;
    drawScenario(data);
    $("download-plan").disabled=false;
  } catch(error) {setStatus("MODEL ERROR: "+error.message);}
  finally {$("run-model").disabled=false;}
}
function downloadPlan() {
  if(!lastPlan) return;
  const blob=new Blob([JSON.stringify(lastPlan,null,2)],{type:"application/json"});
  const address=URL.createObjectURL(blob);
  const link=document.createElement("a");link.href=address;
  link.download="UEV-synthetic-planning-scenario.json";
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(address),1000);
}
async function initialize() {
  initMap();
  try {
    const ds=await api("/api/v1/districts");
    ds.forEach(name=>{const option=document.createElement("option");option.value=name;option.textContent=name;$("district").append(option);});
    await reload();await runModel();
  } catch(error) {setStatus("UNAVAILABLE");$("site-list").replaceChildren(node("div","error",error.message));}
  ["district","lens"].forEach(id=>$(id).addEventListener("change",reload));
  document.querySelectorAll("[data-layer]").forEach(el=>el.addEventListener("change",applyMapLayers));
  $("run-model").addEventListener("click",runModel);
  $("plan-mode").addEventListener("change",updateScenarioControls);
  $("download-plan").addEventListener("click",downloadPlan);
  updateScenarioControls();
}
document.addEventListener("DOMContentLoaded",initialize);
