/* UEV 0.5 GEP/EAE-inspired layer explorer: all user controls are real map operations. */
"use strict";
const EMPTY_GEOJSON={type:"FeatureCollection",features:[]};
const LIVE_COLORS={
  osm_roads:"#e5d18b",osm_transmission:"#ff69c2",
  osm_distribution:"#ffd24d",osm_substations:"#e172e8"
};
const customOverlays=[];
const liveOverlays={};
let publicCatalog=[];
let layerMapReady=false;
function legendStatus(message) {
  const status=$("layer-status");
  if(status)status.textContent=message;
}
function setTab(view) {
  document.querySelectorAll("[data-workspace-tab]").forEach(button=>{
    button.setAttribute("aria-selected",String(button.dataset.workspaceTab===view));
  });
  $("view-layers").hidden=view!=="layers";
  $("view-scenarios").hidden=view!=="scenarios";
}
function catalogRow(layer) {
  const row=node("div","catalog-layer");
  row.dataset.catalogRow=layer.id;
  const label=node("label","catalog-label");
  const status=node("small","source-tag "+layer.status,layer.status==="synthetic"?"DEMO":layer.status==="public"?"PUBLIC":layer.kind==="managed"?"UPLOADED":"SOURCE");
  const head=node("span","catalog-layer-heading",layer.name);
  const caption=node("small","catalog-layer-source",(layer.year?layer.year+" • ":"")+layer.source);
  const textBox=node("span","catalog-layer-text");
  textBox.append(head,caption);
  if(layer.kind==="managed" || layer.status==="public" || layer.status==="synthetic"){
    const check=document.createElement("input");
    check.type="checkbox";
    check.dataset.layer=layer.id;
    check.checked=Boolean(layer.default) || previouslyChecked.has(layer.id);
    check.setAttribute("aria-label","Display "+layer.name);
    check.addEventListener("change",async()=>{
      if(layer.kind==="demo") {
        applyMapLayers();updateLegend();
      }else if(layer.kind==="managed") {
        if(check.checked)await loadManagedLayer(layer);
        else hidePublicLayer(layer.id);
      }else if(layer.kind==="osm") {
        if(check.checked) await refreshPublicLayer(layer.id);
        else hidePublicLayer(layer.id);
      } else if(layer.kind==="population"){
        if(check.checked)await refreshPopulation();else hidePopulation();
      }
    });
    label.append(check,textBox,status);
  } else {
    const a=document.createElement("a");
    a.href=layer.url || "#custom-geojson";
    a.textContent=layer.url?"View source":"Import file";
    a.target=layer.url?"_blank":"";
    if(layer.url) a.rel="noopener noreferrer";
    label.append(textBox,status,a);
  }
  row.append(label,node("div","layer-explanation",layer.description));
  return row;
}
let previouslyChecked=new Set();
function renderCatalog() {
  const catalog=$("layer-catalog");
  catalog.replaceChildren();
  const groups=[...new Set(publicCatalog.map(x=>x.group))];
  for(const group of groups){
    const section=node("section","layer-group");
    section.append(node("h3","",group));
    publicCatalog.filter(x=>x.group===group).forEach(x=>section.append(catalogRow(x)));
    catalog.append(section);
  }
  filterCatalog();
  applyMapLayers();
  updateLegend();
}
function filterCatalog() {
  const term=$("layer-search").value.toLowerCase();
  document.querySelectorAll(".catalog-layer").forEach(el=>{
    el.hidden=!el.textContent.toLowerCase().includes(term);
  });
  document.querySelectorAll(".layer-group").forEach(group=>{
    group.hidden=![...group.querySelectorAll(".catalog-layer")].some(el=>!el.hidden);
  });
}
function viewportBbox() {
  if(!map||!map.isStyleLoaded()) throw Error("Map has not finished loading");
  const box=map.getBounds();
  const b=[box.getWest(),box.getSouth(),box.getEast(),box.getNorth()];
  if(b.some(x=>!Number.isFinite(x)))throw Error("Cannot read map view");
  if((b[2]-b[0])*(b[3]-b[1])>0.30)throw Error("Zoom in to a city or district before loading roads or power lines");
  if(b[0]<29 || b[2]>35.5 || b[1]<-1.6 || b[3]>4.4)throw Error("Zoom into an area within Uganda");
  return b.map(x=>x.toFixed(5)).join(",");
}
function clearPublic(id){
  if(!map)return;
  ["pt","ln","poly"].forEach(part=>{const layer=id+"-"+part;if(map.getLayer(layer))map.removeLayer(layer);});
  if(map.getSource("pub-"+id))map.removeSource("pub-"+id);
}
function paintGeoJSON(id,fc,color) {
  if(!map||!map.isStyleLoaded())throw Error("Map not ready");
  clearPublic(id);
  map.addSource("pub-"+id,{type:"geojson",data:fc});
  const source="pub-"+id;
  const shape=(s)=>["==",["geometry-type"],s];
  map.addLayer({id:id+"-poly",type:"fill",source,filter:shape("Polygon"),
    paint:{"fill-color":color,"fill-opacity":0.22,"fill-outline-color":color}});
  map.addLayer({id:id+"-ln",type:"line",source,
    filter:["any",shape("LineString"),shape("Polygon")],
    paint:{"line-color":color,"line-width":id==="osm_roads"?2:3,"line-opacity":0.9}});
  map.addLayer({id:id+"-pt",type:"circle",source,filter:shape("Point"),
    paint:{"circle-color":color,"circle-radius":6,"circle-stroke-color":"#fff","circle-stroke-width":1.5}});
  const popup=(e)=>{
    if(!e.features?.length)return;
    const p=e.features[0].properties||{};
    const panel=node("div","");
    panel.append(node("strong","",p.name || "Map feature"));
    ["source","voltage","highway","power","ref"].forEach(key=>{
      if(p[key])panel.append(node("p","",key+": "+String(p[key])));
    });
    new maplibregl.Popup({maxWidth:"320px"}).setLngLat(e.lngLat).setDOMContent(panel).addTo(map);
  };
  ["ln","pt","poly"].forEach(part=>map.on("click",id+"-"+part,popup));
}
async function loadManagedLayer(layer) {
  const check=document.querySelector('[data-layer="'+layer.id+'"]');
  if(!check?.checked)return;
  try{
    legendStatus("Loading published dataset: "+layer.name+"…");
    const response=await api("/api/v1/managed/"+encodeURIComponent(layer.id));
    if(!check.checked)return;
    paintGeoJSON(layer.id,response,layer.color||"#24caca");
    liveOverlays[layer.id]={count:response.features.length,source:layer.source};
    legendStatus(layer.name+" • "+response.features.length+" uploaded features. Source: "+layer.source+"; unverified for engineering use.");
    updateLegend();
  }catch(error){
    hidePublicLayer(layer.id);
    legendStatus(layer.name+": "+error.message);
  }
}
async function reloadPublishedCatalog(){
  const checks=[...document.querySelectorAll("input[data-layer]:checked")].map(el=>el.dataset.layer);
  previouslyChecked=new Set(checks);
  try{
    const response=await api("/api/v1/catalog");
    publicCatalog=response.layers;
    const available=new Set(publicCatalog.map(x=>x.id));
    Object.keys(liveOverlays).filter(id=>!available.has(id)).forEach(id=>hidePublicLayer(id));
    renderCatalog();
    legendStatus("Layer catalogue refreshed. Newly published datasets are now available.");
  }catch(error){legendStatus("Cannot refresh catalogue: "+error.message);}
}
async function refreshPublicLayer(id) {
  const checked=document.querySelector('[data-layer="'+id+'"]');
  if(!checked?.checked)return;
  try{
    const bbox=viewportBbox();
    legendStatus("Loading "+id.replace("osm_","")+" mapped features for current map view…");
    const data=await api("/api/v1/public/osm/"+id+"?"+query({bbox}));
    if(!checked.checked)return;
    liveOverlays[id]={count:data.features.length,bbox,source:"OpenStreetMap"};
    paintGeoJSON(id,data,LIVE_COLORS[id]);
    legendStatus(data.features.length+" OSM features loaded. Incomplete public map: NOT an official electricity or road inventory.");
    updateLegend();
  }catch(error){
    delete liveOverlays[id]; clearPublic(id);
    legendStatus(id.replace("osm_","")+": "+error.message);
    updateLegend();
  }
}
function hidePublicLayer(id) {
  delete liveOverlays[id];
  clearPublic(id);
  legendStatus("Public layer hidden. Enable or refresh to load another map view.");
  updateLegend();
}
function hidePopulation(){
  if(!map)return;
  if(map.getLayer("population-raster"))map.removeLayer("population-raster");
  if(map.getSource("population-raster"))map.removeSource("population-raster");
  delete liveOverlays.population_2020;
  updateLegend();
}
async function refreshPopulation(){
  if(!map||!map.isStyleLoaded())return;
  const check=document.querySelector('[data-layer="population_2020"]');
  if(!check?.checked)return;
  try{
    const b=map.getBounds(), arr=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()];
    const area=(arr[2]-arr[0])*(arr[3]-arr[1]);
    if(area>5 || arr[0]<29 || arr[2]>35.5 || arr[1]<-1.6 || arr[3]>4.4)
      throw Error("Zoom into a district or smaller area within Uganda for the population raster");
    hidePopulation();
    const bbox=arr.map(n=>n.toFixed(5)).join(",");
    const url="/api/v1/public/population.png?"+query({bbox});
    const corners=[[arr[0],arr[3]],[arr[2],arr[3]],[arr[2],arr[1]],[arr[0],arr[1]]];
    map.addSource("population-raster",{type:"image",url,coordinates:corners});
    // Keep population beneath the network and demonstration overlays.
    map.addLayer({id:"population-raster",type:"raster",source:"population-raster",
      paint:{"raster-opacity":0.50,"raster-resampling":"linear"}},
      map.getLayer("points-charging")?"points-charging":undefined);
    liveOverlays.population_2020={count:1,source:"WorldPop historical 2020 raster"};
    legendStatus("WorldPop historical population raster requested (2020; not 2026).");
    updateLegend();
  }catch(error){legendStatus("Population: "+error.message);hidePopulation();}
}
async function refreshAllPublic() {
  const selected=publicCatalog.filter(x=>x.kind==="osm"&&
    document.querySelector('[data-layer="'+x.id+'"]')?.checked);
  for(const layer of selected)await refreshPublicLayer(layer.id);
  if(document.querySelector('[data-layer="population_2020"]')?.checked)await refreshPopulation();
  if(!selected.length&&!document.querySelector('[data-layer="population_2020"]')?.checked)
    legendStatus("Select a public layer first; switch to Scenarios to perform EV modelling.");
}
function updateLegend(){
  const legend=$("active-map-legend");
  if(!legend)return;
  const active=publicCatalog.filter(x=>document.querySelector('[data-layer="'+x.id+'"]')?.checked);
  const messages=active.map(x=>{
    const v=liveOverlays[x.id];
    return x.name+" ("+(x.status==="synthetic"?"DEMO":v?(v.count+" features"):"not loaded")+")";
  });
  if(customOverlays.length)messages.push(customOverlays.length+" custom file(s)");
  legend.textContent=messages.length?"Visible selections: "+messages.join(" · "):"No layers selected";
}
function importGeoJSONFile(file){
  if(file.size>8_000_000)throw Error("GeoJSON must be smaller than 8 MB");
  return file.text().then(text=>{
    const payload=JSON.parse(text);
    if(!["FeatureCollection","Feature"].includes(payload.type))throw Error("Expected GeoJSON FeatureCollection or Feature");
    const features=payload.type==="FeatureCollection"?payload.features:[payload];
    if(!Array.isArray(features)||features.length>5000)throw Error("Maximum 5,000 GeoJSON features");
    const kinds=["Point","MultiPoint","LineString","MultiLineString","Polygon","MultiPolygon"];
    if(features.some(f=>f.type!=="Feature"||!f.geometry||!kinds.includes(f.geometry.type)))
      throw Error("Invalid or unsupported GeoJSON geometry");
    return {type:"FeatureCollection",features};
  });
}
async function addCustomFile(file){
  try{
    const data=await importGeoJSONFile(file);
    if(!map?.isStyleLoaded())throw Error("Map has not finished loading");
    const id="custom-"+customOverlays.length;
    paintGeoJSON(id,data,"#28d5db");
    customOverlays.push(id);
    const row=node("div","custom-row");
    const checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.checked=true;
    checkbox.setAttribute("aria-label","Show "+file.name);
    checkbox.addEventListener("change",()=>{
      ["poly","ln","pt"].forEach(k=>{
        const layer=id+"-"+k;
        if(map.getLayer(layer))map.setLayoutProperty(layer,"visibility",checkbox.checked?"visible":"none");
      });
    });
    row.append(checkbox,node("span","",file.name+" • "+data.features.length+" features"));
    $("custom-list").append(row);
    legendStatus(file.name+" added locally. It will NOT automatically affect EV model parameters.");
    updateLegend();
  }catch(error){legendStatus("Cannot open custom GeoJSON: "+error.message);}
}
async function initializeLayerExplorer(){
  document.querySelectorAll("[data-workspace-tab]").forEach(btn=>
    btn.addEventListener("click",()=>setTab(btn.dataset.workspaceTab)));
  setTab("layers");
  $("layer-search").addEventListener("input",filterCatalog);
  $("refresh-layers").addEventListener("click",refreshAllPublic);
  $("reload-catalog").addEventListener("click",reloadPublishedCatalog);
  $("custom-geojson").addEventListener("change",e=>{
    const file=e.target.files?.[0];if(file)addCustomFile(file);
    e.target.value="";
  });
  try{
    const data=await api("/api/v1/catalog");
    publicCatalog=data.layers;
    renderCatalog();
  }catch(error){legendStatus("Catalog not available: "+error.message);}
}
document.addEventListener("DOMContentLoaded",initializeLayerExplorer);
