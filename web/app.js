"use strict";
const LAYERS = ["charging", "candidates", "grid", "mobility"];
const COLORS = {charging:"#f09a2b", candidates:"#00877e", grid:"#9c68e8", mobility:"#338ee0"};
const mapCache = {};
let map = null;
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
  });
}
function applyMapLayers() {
  if (!map || !map.isStyleLoaded()) return;
  LAYERS.forEach(layer => {
    const featureCollection = mapCache[layer] || {type:"FeatureCollection",features:[]};
    const source = map.getSource("data-"+layer);
    if (source) source.setData(featureCollection);
    const toggle = document.querySelector(`[data-layer="${layer}"]`);
    if (map.getLayer("points-"+layer)) map.setLayoutProperty("points-"+layer,"visibility",toggle.checked?"visible":"none");
  });
}
function focusLocation(lon,lat) {
  if (map) map.flyTo({center:[lon,lat],zoom:12,essential:true});
}
async function reload() {
  const area = selected();
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
async function runModel() {
  const year=Number($("year").value),pct=Number($("target").value);
  if(!Number.isInteger(year)||year<2026||year>2200||!Number.isFinite(pct)||pct<0||pct>100){setStatus("INVALID INPUTS");return;}
  setStatus("CALCULATING…");
  try {
    const data=await api("/api/v1/model/preview?"+query({district:$("district").value,target_year:year,target_pct:pct,technology:$("technology").value}));
    $("r-ev").textContent=nice(data.future_evs);
    $("r-energy").textContent=nice(data.grid_mwh_per_year)+" MWh";
    $("r-chargers").textContent=nice(data.number_of_chargers);
    $("r-cost").textContent="$"+nice(data.infrastructure_capex_proxy);
    setStatus("SYNTHETIC PREVIEW");
  } catch(error) {setStatus("ERROR: "+error.message);}
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
}
document.addEventListener("DOMContentLoaded",initialize);
