"""Static frontend integration checks; these do not replace browser E2E testing."""
import re
from fastapi.testclient import TestClient
from uev.api import create_app
from uev import geo

WEB = geo.ROOT / "web"

def test_javascript_references_existing_html_control_ids():
    html=(WEB/"index.html").read_text(encoding="utf-8")
    js=(WEB/"app.js").read_text(encoding="utf-8")
    existing=set(re.findall(r'id="([^"]+)"',html))
    referenced=set(re.findall(r'\$\("([^"]+)"\)',js))
    assert referenced <= existing, "Missing HTML controls: "+str(sorted(referenced-existing))

def test_interface_served_with_integrated_controls(tmp_path):
    with TestClient(create_app(tmp_path/"ui.sqlite")) as client:
        response=client.get("/")
        assert response.status_code==200
        for name in ("plan-mode","manual-sites","energy-coverage","modules-site",
                     "run-model","r-coverage","download-plan"):
            assert f'id="{name}"' in response.text
        assert client.get("/static/app.js").status_code == 200
