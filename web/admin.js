"use strict";
let storedLayers=[];
let selectedLayerFile=null;
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
async function inspectFile(file) {
  const extension=(file.name.split(".").pop()||"").toLowerCase();
  if(!["geojson","json","csv","zip","gpkg"].includes(extension))
    throw Error("Unsupported file type: "+extension+". Use GeoJSON, CSV coordinates, zipped Shapefile, or GeoPackage. GeoTIFF population rasters are not yet supported.");
  if(!file.size || file.size>20_000_000)
    throw Error("Input file must not be empty or exceed 20 MB.");
  if(extension==="geojson" || extension==="json"){
    let data;
    try {data=JSON.parse(await file.text());}
    catch(_) {throw Error("GeoJSON is not valid JSON. Re-export from QGIS as GeoJSON (EPSG:4326).");}
    if(data.type==="Feature")data={type:"FeatureCollection",features:[data]};
    if(data.type!=="FeatureCollection"||!Array.isArray(data.features))
      throw Error("GeoJSON must contain a FeatureCollection.");
    if(!data.features.length||data.features.length>5000)
      throw Error("GeoJSON needs 1–5,000 features.");
    return viewSummary(data)+". Ready to import as a private draft.";
  }
  if(extension==="zip")return "Zipped Shapefile selected. Include .shp, .shx, .dbf and EPSG:4326 .prj files.";
  if(extension==="csv")return "CSV selected. A longitude and latitude column is required.";
  return "GeoPackage selected. One EPSG:4326 vector layer is supported.";
}
function importFeedback(message,error=false){
  const status=$("import-status");
  if(status){status.textContent=message;status.className=error?"import-feedback error":"import-feedback success";}
  toast(message,error);
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
  const file=selectedLayerFile;
  if(!file){importFeedback("First select a supported GIS file, then complete the metadata.",true);return;}
  const yearText=$("layer-year").value.trim();
  const payload=new FormData();
  payload.append("file",file,file.name);
  payload.append("name",$("layer-name").value);
  payload.append("description",$("layer-description").value || "User uploaded map layer, not independently verified.");
  payload.append("category",$("layer-category").value);
  payload.append("source",$("layer-source").value);
  payload.append("license",$("layer-license").value);
  payload.append("reference_year",yearText);
  payload.append("color",$("layer-color").value);
  $("upload-button").disabled=true;
  importFeedback("Importing "+file.name+"…");
  try{
    // Browser sets multipart/form-data boundary automatically; do NOT set Content-Type.
    const result=await request("/api/admin/files",{method:"POST",body:payload});
    selectedLayerFile=null;
    $("layer-form").reset();
    $("file-summary").textContent="No file selected.";
    importFeedback(result.name+" saved as a PRIVATE draft. "+result.import_summary+". Review it before publishing.");
    await loadLibrary();
    await previewDataset(result);
  }catch(error){
    importFeedback("Import failed: "+error.message,true);
  }finally{$("upload-button").disabled=false;}
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
    selectedLayerFile=null;
    const file=event.target.files?.[0];
    if(!file)return;
    try{
      const summary=await inspectFile(file);
      selectedLayerFile=file;
      $("file-summary").textContent=summary;
      if(!$("layer-name").value)$("layer-name").value=file.name.replace(/\.(geojson|json|csv|zip|gpkg)$/i,"");
      importFeedback("File recognised: "+file.name+". Add source and licence, then select Import as private draft.");
    }catch(error){
      $("file-summary").textContent=error.message;
      importFeedback(error.message,true);
    }
  });
  try{await request("/api/admin/session");initMap();await loadLibrary();}
  catch(e){toast("Access denied or Data Manager not configured: "+e.message,true);}
}
document.addEventListener("DOMContentLoaded",init);
