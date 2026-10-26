"""Public-data overlay catalogue for UEV. Never a source of grid-capacity certification.

OSM features are limited to a bounding box chosen by the user. The catalog
separates demonstrative platform assets, publicly fetchable mapped objects and
external data products that need preparation/licensing.
"""
from __future__ import annotations

from math import isfinite
from urllib.parse import urlencode
import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WORLDPOP_IMAGE = "https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Total_Population_100m/ImageServer/exportImage"

CATALOG = [
    {"id": "population_2020", "name": "Population surface (WorldPop archive)", "group": "Population & settlements",
     "kind": "population", "status": "public", "source": "WorldPop / Esri", "year": 2020,
     "description": "Historical gridded population; not current 2026 EV demand", "default": False},
    {"id": "population_2026", "name": "Population 2026 (WorldPop Global2)", "group": "Population & settlements",
     "kind": "external", "status": "download", "source": "WorldPop", "year": 2026,
     "description": "Available as a 100m GeoTIFF; prepare an overlay for integration, not yet live map tiles",
     "url": "https://hub.worldpop.org/geodata/summary?id=75840", "default": False},
    {"id": "osm_roads", "name": "Road network", "group": "Transport & accessibility",
     "kind": "osm", "status": "public", "source": "OpenStreetMap contributors", "year": None,
     "description": "Mapped road geometries within current view, not validated road travel time", "default": False},
    {"id": "osm_transmission", "name": "Transmission (OSM mapped)", "group": "Electricity infrastructure",
     "kind": "osm", "status": "public", "source": "OpenStreetMap contributors", "year": None,
     "description": "Power=line ways; voltage tags preserved where available. Unverified classification", "default": False},
    {"id": "osm_distribution", "name": "Distribution (OSM mapped)", "group": "Electricity infrastructure",
     "kind": "osm", "status": "public", "source": "OpenStreetMap contributors", "year": None,
     "description": "Power=minor_line ways. Highly incomplete; NOT a utility distribution-network GIS", "default": False},
    {"id": "osm_substations", "name": "Substations & transformers (OSM)", "group": "Electricity infrastructure",
     "kind": "osm", "status": "public", "source": "OpenStreetMap contributors", "year": None,
     "description": "Publicly mapped electrical assets, no confirmed feeder headroom", "default": False},
    {"id": "charging", "name": "Charging / swapping (demo)", "group": "EV & mobility",
     "kind": "demo", "status": "synthetic", "source": "UEV synthetic", "year": 2026,
     "description": "Invented charging sites; not actual stations", "default": True},
    {"id": "candidates", "name": "Candidate locations (demo)", "group": "EV & mobility",
     "kind": "demo", "status": "synthetic", "source": "UEV synthetic", "year": 2026,
     "description": "Hypothetical sites with scenario screening scores", "default": True},
    {"id": "mobility", "name": "EV activity hotspots (demo)", "group": "EV & mobility",
     "kind": "demo", "status": "synthetic", "source": "UEV synthetic", "year": 2026,
     "description": "Fictional activity weights, not observed travel", "default": True},
    {"id": "grid", "name": "Example grid nodes (demo)", "group": "Electricity infrastructure",
     "kind": "demo", "status": "synthetic", "source": "UEV synthetic", "year": 2026,
     "description": "Not verified Ugandan transformers or feeders", "default": False},
    {"id": "districts", "name": "Official district boundaries", "group": "Boundaries & environment",
     "kind": "external", "status": "needs_data", "source": "UBOS / government",
     "year": None, "description": "Import a licensed polygon layer; example district labels are NOT boundaries", "default": False},
    {"id": "solar", "name": "Solar resource (Global Solar Atlas)", "group": "Boundaries & environment",
     "kind": "external", "status": "download", "source": "Global Solar Atlas / ESMAP", "year": None,
     "description": "Source available for PV-charging studies; raster integration is future work",
     "url": "https://globalsolaratlas.info", "default": False},
    {"id": "landuse", "name": "Land use / restrictions", "group": "Boundaries & environment",
     "kind": "external", "status": "needs_data", "source": "Licensed GIS provider", "year": None,
     "description": "Upload verified GeoJSON to assess siting exclusions; not bundled", "default": False},
]

OSM_SELECTORS = {
    "osm_roads": 'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street)$"]',
    "osm_transmission": 'way["power"="line"]',
    "osm_distribution": 'way["power"="minor_line"]',
    "osm_substations": 'node["power"~"^(substation|transformer)$"];way["power"="substation"]',
}

def validate_bbox(value: str, *, area_limit: float = 0.30) -> tuple[float,float,float,float]:
    try:
        west, south, east, north = [float(part) for part in value.split(",")]
    except (ValueError, TypeError) as exc:
        raise ValueError("bbox must be west,south,east,north") from exc
    if not all(map(isfinite, (west,south,east,north))):
        raise ValueError("Bounding box coordinates must be finite")
    if west >= east or south >= north or west < -180 or east > 180 or south < -90 or north > 90:
        raise ValueError("Invalid geographic bounding box")
    if (east-west)*(north-south) > area_limit:
        raise ValueError("Zoom in to a city or district area to load public map data (maximum 0.30 square degrees)")
    # Limited to Uganda; avoid becoming an uncontrolled global Overpass proxy.
    if not 29 <= west <= 35.5 or not -1.6 <= south <= 4.4 or east > 35.5 or north > 4.4:
        raise ValueError("This version supports public layers within Uganda only")
    return west,south,east,north

def build_osm_query(layer: str, bbox: tuple[float,float,float,float]) -> str:
    if layer not in OSM_SELECTORS:
        raise ValueError("Unknown OSM layer")
    west,south,east,north=bbox
    suffix=f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
    filters=OSM_SELECTORS[layer].split(";")
    ways="".join(f"{s}{suffix};" for s in filters if s)
    return f"[out:json][timeout:20];({ways});out geom;"

def convert_osm(elements: list[dict], layer: str) -> dict:
    if layer not in OSM_SELECTORS: raise ValueError("Unknown OSM layer")
    features=[]
    for item in elements[:12000]:
        tags=item.get("tags",{})
        geometry=item.get("geometry") or []
        if item.get("type")=="node":
            pos=[item.get("lon"),item.get("lat")]
            if any(not isinstance(v,(int,float)) for v in pos):continue
            shape={"type":"Point","coordinates":pos}
        elif len(geometry)>1:
            coords=[[node.get("lon"),node.get("lat")] for node in geometry]
            if any(any(not isinstance(v,(int,float)) for v in point) for point in coords):continue
            shape={"type":"LineString","coordinates":coords}
        else:
            continue
        props={"name":tags.get("name") or (layer.replace("osm_","").title()+" / "+str(item.get("id"))),
               "layer":layer,"source":"OpenStreetMap","status":"public_unverified",
               "voltage":tags.get("voltage"),"highway":tags.get("highway"),
               "power":tags.get("power"),"ref":tags.get("ref")}
        features.append({"type":"Feature","id":f"{item.get('type')}/{item.get('id')}",
                         "geometry":shape,"properties":props})
    return {"type":"FeatureCollection","features":features,
            "metadata":{"source":"© OpenStreetMap contributors / ODbL",
                        "scope":"Only mapped OSM features intersecting the current query area; incomplete coverage",
                        "verified_electrical_assets":False}}

async def load_osm(layer: str, bbox: str) -> dict:
    coords=validate_bbox(bbox)
    expression=build_osm_query(layer,coords)
    async with httpx.AsyncClient(timeout=28,follow_redirects=False) as client:
        response=await client.post(OVERPASS_URL, data={"data":expression},
                                   headers={"User-Agent":"UEV-GIS-Research-Prototyping/0.5"})
        response.raise_for_status()
        if len(response.content)>8_000_000:
            raise ValueError("OSM response too large; zoom in further")
        data=response.json()
    return convert_osm(data.get("elements",[]),layer)

async def population_png(bbox: str) -> bytes:
    west,south,east,north=validate_bbox(bbox,area_limit=5)
    params={"f":"image","bbox":f"{west},{south},{east},{north}",
            "bboxSR":4326,"imageSR":4326,"size":"900,900",
            "format":"png32","transparent":"true",
            "time":"2020-01-01,2020-12-31"}
    async with httpx.AsyncClient(timeout=30) as client:
        response=await client.get(WORLDPOP_IMAGE,params=params)
        response.raise_for_status()
        if not response.headers.get("content-type","").startswith("image/"):
            raise ValueError("The WorldPop image service did not return a map image")
        if len(response.content)>8_000_000:
            raise ValueError("Population image too large")
    return response.content
