"use strict";
let storedLayers=[];
let chosenGeoJSON=null;
let adminMap=null;
let previewLayerId=null;
const $=id=>document.getElementById(id);
function el(tag,css,content) {
  const element=document.createElement(tag);
  if(css)element.className=css;
  if(content!==undefined)element.textContent=String(content);
  return element;
}
function toast(message,error=false){
  $("toast").textContent=message;
  $("toast").className=error?"error":"good";
}
async function request(path,options={}){
  const response=await fetch(path,{credentials:"same-origin",cache:"no-store",...options});
  if(!response.ok){
    let reason="Request failed ("+response.status+")";
    try{const msg=await response.json();reason=msg.detail||reason;}catch(_){}
    throw new Error(typeof reason==="string"?reason:JSON.stringify(reason));
  }
  if(response.status===204)return null;
  return response.json();
}
async function readFile(file) {
  if(!file || file.size>5_000_000)throw Error("Select a GeoJSON file smaller than 5 MB.");
  const document=JSON.parse(await file.text());
  if(document.type!=="FeatureCollection" || !Array.isArray(document.features))
    throw Error("File must be a GeoJSON FeatureCollection.");
  if(!document.features.length || document.features.length>5000)
    throw Error("File must contain 1–5,000 features.");
  return document;
}
function viewSummary(document){
  const kinds={};
  document.features.forEach(feature=>{
    const kind=feature.geometry?.type||"Unknown";
    kinds[kind]=(kinds[kind]||0)+1;
  });
  return document.features.length+" features • "+Object.entries(kinds).map(([kind,n])=>kind+": "+n).join(", ");
}
async function loadLibrary(){
  try{
    const result=await request("/api/admin/layers");
    storedLayers=result.layers;
    $("count-all").textContent=storedLayers.length;
    $("count-published").textContent=storedLayers.filter(x=>x.published).length;
    $("count-drafts").textContent=storedLayers.filter(x=>!x.published).length;
    const list=$("layer-list");list.replaceChildren();
    if(!storedLayers.length)list.append(el("p","help","No datasets yet. Import a GeoJSON file to begin."));
    for(const layer of storedLayers){
      const row=el("article","dataset");
      const main=el("div","dataset-main");
      main.append(el("strong","",layer.name));
      main.append(el("small","",layer.category+" • "+layer.feature_count+" features • "+layer.source));
      main.append(el("small","", "Licence: "+layer.license+" • "+(layer.reference_year||"undated")));
      const pill=el("span","pill "+(layer.published?"published":"draft"),layer.published?"PUBLISHED":"PRIVATE DRAFT");
      const actions=el("div","dataset-actions");
      const preview=el("button","secondary","Preview");
      preview.type="button";preview.addEventListener("click",()=>previewDataset(layer));
      const publish=el("button",layer.published?"secondary":"primary",layer.published?"Unpublish":"Publish");
      publish.type="button";publish.addEventListener("click",()=>updatePublication(layer));
      const remove=el("button","danger","Delete");
      remove.type="button";remove.addEventListener("click",()=>deleteDataset(layer));
      actions.append(preview,publish,remove);
      row.append(main,pill,actions);
      list.append(row);
    }
  }catch(e){toast(e.message,true);}
}
async function uploadDataset(event){
  event.preventDefault();
  if(!chosenGeoJSON){toast("Choose and review your GeoJSON first.",true);return;}
  const yearText=$("layer-year").value.trim();
  const payload={
    name:$("layer-name").value,
    description:$("layer-description").value || "User-uploaded GIS overlay; check source before use.",
    category:$("layer-category").value,
    source:$("layer-source").value,
    license:$("layer-license").value,
    reference_year:yearText?Number(yearText):null,
    color:$("layer-color").value,
    geojson:chosenGeoJSON
  };
  $("upload-button").disabled=true;
  toast("Importing the dataset…");
  try {
    const result=await request("/api/admin/layers",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });
    toast(result.name+" saved as PRIVATE draft. Preview it, then publish if appropriate.");
    chosenGeoJSON=null;
    $("layer-form").reset();
    $("file-summary").textContent="Max 5 MB, 5,000 features. File is not selected.";
    await loadLibrary();
    await previewDataset(result);
  }catch(e){toast(e.message,true);}
  finally{$("upload-button").disabled=false;}
}
async function updatePublication(layer){
  if(!layer.published){
    const accepted=confirm(
      "PUBLISH '"+layer.name+"'?\n\nEvery feature and every attribute in this GeoJSON "+
      "will become available to public UEV Explorer users. Confirm the source's "+
      "licence, permission and privacy requirements before continuing.");
    if(!accepted)return;
  }else{
    if(!confirm("Remove '"+layer.name+"' from the public explorer?"))return;
  }
  try{
    await request("/api/admin/layers/"+encodeURIComponent(layer.id)+"/publication",{
      method:"PUT",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({published:!layer.published})
    });
    toast(layer.name+(layer.published?" is now private.":" is now published. Refresh the public explorer catalogue."));
    await loadLibrary();
  }catch(e){toast(e.message,true);}
}
async function deleteDataset(layer){
  if(!confirm("Permanently DELETE '"+layer.name+"' and all its imported features?"))return;
  try{
    await request("/api/admin/layers/"+encodeURIComponent(layer.id),{method:"DELETE"});
    if(previewLayerId===layer.id){previewLayerId=null;clearPreview();}
    toast("Deleted "+layer.name);
    await loadLibrary();
  }catch(e){toast(e.message,true);}
}
function initMap(){
  if(!window.maplibregl){
    $("admin-map").replaceChildren(el("div","map-placeholder","Map unavailable: check your internet connection."));
    return;
  }
  adminMap=new maplibregl.Map({
    container:"admin-map",center:[32.6,.8],zoom:6.2,
    style:{version:8,sources:{osm:{type:"raster",tileSize:256,
      tiles:["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      attribution:"© OpenStreetMap contributors"}},
      layers:[{id:"osm",type:"raster",source:"osm"}]}
  });
  adminMap.addControl(new maplibregl.NavigationControl(),"bottom-right");
}
function clearPreview(){
  if(!adminMap||!adminMap.isStyleLoaded())return;
  ["preview-points","preview-lines","preview-polygons"].forEach(id=>{
    if(adminMap.getLayer(id))adminMap.removeLayer(id);
  });
  if(adminMap.getSource("preview"))adminMap.removeSource("preview");
}
function allPositions(coords,out){
  if(!Array.isArray(coords))return;
  if(coords.length>=2 && typeof coords[0]==="number" && typeof coords[1]==="number"){
    out.push([coords[0],coords[1]]);
  }else coords.forEach(child=>allPositions(child,out));
}
function paintPreview(geojson,color){
  if(!adminMap){return;}
  if(!adminMap.isStyleLoaded()){
    adminMap.once("load",()=>paintPreview(geojson,color));return;
  }
  clearPreview();
  adminMap.addSource("preview",{type:"geojson",data:geojson});
  const source="preview";
  adminMap.addLayer({id:"preview-polygons",type:"fill",source,
    filter:["==",["geometry-type"],"Polygon"],
    paint:{"fill-color":color,"fill-opacity":.26}});
  adminMap.addLayer({id:"preview-lines",type:"line",source,
    filter:["any",["==",["geometry-type"],"LineString"],["==",["geometry-type"],"Polygon"]],
    paint:{"line-color":color,"line-width":3}});
  adminMap.addLayer({id:"preview-points",type:"circle",source,
    filter:["==",["geometry-type"],"Point"],
    paint:{"circle-color":color,"circle-radius":7,"circle-stroke-color":"white","circle-stroke-width":2}});
  const coords=[];
  geojson.features.forEach(feature=>allPositions(feature.geometry.coordinates,coords));
  if(coords.length){
    const bounds=new maplibregl.LngLatBounds(coords[0],coords[0]);
    coords.forEach(p=>bounds.extend(p));
    adminMap.fitBounds(bounds,{padding:65,maxZoom:12,duration:650});
  }
}
async function previewDataset(layer){
  previewLayerId=layer.id;
  try{
    const data=await request("/api/admin/layers/"+encodeURIComponent(layer.id)+"/geojson");
    $("preview-meta").textContent=layer.name+" • "+viewSummary(data)+" • "+
      (layer.published?"PUBLIC":"PRIVATE DRAFT")+" • Uploaded, not independently verified.";
    paintPreview(data,layer.color);
    toast("Previewing "+layer.name);
  }catch(e){toast(e.message,true);}
}
async function init(){
  $("layer-form").addEventListener("submit",uploadDataset);
  $("refresh-list").addEventListener("click",loadLibrary);
  $("geojson-file").addEventListener("change",async(event)=>{
    chosenGeoJSON=null;
    const file=event.target.files?.[0];
    if(!file)return;
    try {
      chosenGeoJSON=await readFile(file);
      $("file-summary").textContent=viewSummary(chosenGeoJSON);
      if(!$("layer-name").value)$("layer-name").value=file.name.replace(/\.(geojson|json)$/i,"");
      toast("GeoJSON parsed. Complete the metadata and import it as a private draft.");
    }catch(e){
      $("file-summary").textContent=e.message;
      toast(e.message,true);
    }
  });
  try{await request("/api/admin/session");initMap();await loadLibrary();}
  catch(e){toast("Access denied or Data Manager not configured: "+e.message,true);}
}
document.addEventListener("DOMContentLoaded",init);
