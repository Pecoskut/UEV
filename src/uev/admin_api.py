"""Private UEV data-manager application (separate process and port).

Start with: uvicorn uev.admin_api:app --host 127.0.0.1 --port 8002
Public explorer: uvicorn uev.api:app --host 127.0.0.1 --port 8001

The admin app is intentionally NOT mounted within the public API.
HTTP Basic is for trusted local use only; production requires HTTPS, identity
management, audit logs, and access policies.
"""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from . import geo, managed_layers

WEB = geo.ROOT / "web"
basic = HTTPBasic(realm="UEV Data Manager")

def require_admin(credentials: HTTPBasicCredentials = Depends(basic)):
    username=os.environ.get("UEV_ADMIN_USER","")
    password=os.environ.get("UEV_ADMIN_PASSWORD","")
    if not username or len(password)<12:
        raise HTTPException(503,"Configure UEV_ADMIN_USER and a UEV_ADMIN_PASSWORD of 12+ characters")
    valid=hmac.compare_digest(credentials.username.encode(),username.encode())
    valid &= hmac.compare_digest(credentials.password.encode(),password.encode())
    if not valid:
        raise HTTPException(401,detail="Invalid administrator credentials",
                            headers={"WWW-Authenticate":'Basic realm="UEV Data Manager"'})
    return True

def guard_mutation(request: Request):
    origin=request.headers.get("origin")
    if origin:
        url=urlsplit(origin)
        if url.scheme!=request.url.scheme or url.netloc!=request.url.netloc:
            raise HTTPException(403,"Cross-origin changes are not permitted")
    if request.headers.get("content-type","").split(";")[0].strip().lower()!="application/json":
        raise HTTPException(415,"Submit JSON with Content-Type: application/json")
    if request.headers.get("content-length") and int(request.headers["content-length"])>managed_layers.MAX_BYTES+40000:
        raise HTTPException(413,"Layer upload exceeds size limit")

async def read_json_request(request: Request):
    guard_mutation(request)
    data=await request.body()
    if len(data)>managed_layers.MAX_BYTES+40000:
        raise HTTPException(413,"Layer upload exceeds size limit")
    try:
        payload=json.loads(data)
    except (UnicodeDecodeError,ValueError) as exc:
        raise HTTPException(422,"Request body is not valid JSON") from exc
    if not isinstance(payload,dict):
        raise HTTPException(422,"Expected a JSON object")
    return payload

def create_admin_app(db_path: str | Path | None=None):
    path=Path(db_path or os.environ.get("UEV_DB_PATH") or (Path.home()/".uev"/"uev-demo.sqlite"))
    with geo.connect(path) as conn:
        managed_layers.ensure_schema(conn)
    app=FastAPI(title="UEV Private Data Manager",version="0.6.0",
                description="Local privileged layer-upload and publication interface")
    app.mount("/assets",StaticFiles(directory=WEB),name="assets")

    def _db():
        return geo.connect(path)

    @app.get("/")
    def admin_index(_:bool=Depends(require_admin)):
        return FileResponse(WEB/"admin.html",headers={"Cache-Control":"no-store"})

    @app.get("/api/admin/session")
    def admin_status(_:bool=Depends(require_admin)):
        return {"authenticated":True,"role":"administrator","version":"0.6.0"}

    @app.get("/api/admin/layers")
    def admin_list(_:bool=Depends(require_admin)):
        with _db() as conn:
            return {"layers":managed_layers.list_layers(conn),
                    "warning":"Unpublished layers are private to the local admin service. Publishing exposes the entire uploaded GeoJSON through the public explorer."}

    @app.get("/api/admin/layers/{ident}/geojson")
    def admin_preview(ident:str,_:bool=Depends(require_admin)):
        with _db() as conn:
            layer=managed_layers.get_layer(conn,ident,published_only=False)
        if layer is None:raise HTTPException(404,"Layer not found")
        return layer

    @app.post("/api/admin/layers",status_code=201)
    async def admin_upload(request:Request,_:bool=Depends(require_admin)):
        payload=await read_json_request(request)
        try:
            with _db() as conn:
                return managed_layers.create_layer(conn,payload)
        except ValueError as exc:
            raise HTTPException(422,detail=str(exc)) from exc

    @app.put("/api/admin/layers/{ident}/publication")
    async def admin_publish(ident:str,request:Request,_:bool=Depends(require_admin)):
        payload=await read_json_request(request)
        try:
            with _db() as conn:
                result=managed_layers.set_publication(conn,ident,payload.get("published"))
        except ValueError as exc:
            raise HTTPException(422,detail=str(exc)) from exc
        if result is None:raise HTTPException(404,"Layer not found")
        return result

    @app.delete("/api/admin/layers/{ident}",status_code=204)
    def admin_delete(ident:str,request:Request,_:bool=Depends(require_admin)):
        origin=request.headers.get("origin")
        if origin:
            url=urlsplit(origin)
            if url.scheme!=request.url.scheme or url.netloc!=request.url.netloc:
                raise HTTPException(403,"Cross-origin changes are not permitted")
        with _db() as conn:
            removed=managed_layers.remove_layer(conn,ident)
        if not removed:raise HTTPException(404,"Layer not found")
        return Response(status_code=204)

    return app

app=create_admin_app()
