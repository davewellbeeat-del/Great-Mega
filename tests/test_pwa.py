import json, os, re, struct, sys, tempfile

_TMP = tempfile.TemporaryDirectory()
os.environ["GREAT_MEGA_DATA"] = _TMP.name
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from app import app


def anon():
    return app.test_client()


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


def test_manifest_is_valid_and_icons_exist():
    r = anon().get("/manifest.webmanifest")
    assert r.status_code == 200 and "manifest+json" in r.mimetype
    m = json.loads(r.data)
    assert m["display"] == "standalone" and m["start_url"] == "/" and m["name"]
    sizes = {i["sizes"]: i for i in m["icons"]}
    assert "192x192" in sizes and "512x512" in sizes
    assert any(i.get("purpose") == "maskable" for i in m["icons"])
    for icon in m["icons"]:
        w, h = map(int, icon["sizes"].split("x"))
        assert png_size(os.path.join(ROOT, icon["src"].lstrip("/"))) == (w, h), icon["src"]
        assert anon().get(icon["src"]).status_code == 200


def test_service_worker_headers_and_shell_files():
    r = anon().get("/sw.js")
    assert r.status_code == 200 and "javascript" in r.mimetype
    assert "no-cache" in r.headers["Cache-Control"]
    shell = re.search(r"const SHELL = \[(.*?)\];", r.get_data(as_text=True), re.S).group(1)
    urls = re.findall(r'"([^"]+)"', shell)
    assert urls and all(anon().get(u).status_code == 200 for u in urls), urls        # install can't fail on a 404


def test_service_worker_never_caches_api():
    js = open(os.path.join(ROOT, "static", "sw.js")).read()
    assert 'startsWith("/api/")' in js and "return;" in js.split('startsWith("/api/")')[1][:80]


def test_pages_have_app_tags():
    html = anon().get("/", base_url="http://localhost").get_data(as_text=True)
    for needle in ('rel="manifest"', 'rel="apple-touch-icon"', 'name="theme-color"',
                   "viewport-fit=cover", "apple-mobile-web-app-capable", 'id="installBtn"'):
        assert needle in html, needle
    assert "GREAT MEGA" in anon().get("/offline").get_data(as_text=True)


def test_apple_icon_and_ico_exist():
    assert png_size(os.path.join(ROOT, "static/icons/apple-touch-icon.png")) == (180, 180)
    assert os.path.getsize(os.path.join(ROOT, "static/icons/app.ico")) > 1000


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn(); print("ok", name)
    finally:
        _TMP.cleanup()
