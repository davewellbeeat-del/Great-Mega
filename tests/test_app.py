import os, sys, tempfile

# Use a throwaway data folder so tests never touch your real bots or password.
_TMP = tempfile.TemporaryDirectory()
os.environ["GREAT_MEGA_DATA"] = _TMP.name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app
from bots import registry


def setup_module():
    registry.reload()


def teardown_module():
    registry.stop_all()


def c():
    client = app.test_client()
    client.environ_base["HTTP_X_REQUESTED_WITH"] = "GreatMega"     # the header our own pages send
    return client


def test_pages_load():
    client = c()
    html = client.get("/").get_data(as_text=True)
    assert "GREAT MEGA" in html and "Market Watch" in html and "Quick Actions" in html
    for path in ("/static/css/style.css", "/static/js/app.js", "/static/js/theme.js"):
        assert client.get(path).status_code == 200, path


def test_seed_bots():
    st = c().get("/api/state").get_json()
    names = [b["name"] for b in st["bots"]]
    assert names == ["GREAT M", "FURY FLIPPER 2", "FURY FLIPPER 3", "FURY FLIPPER 4", "FURY FLIPPER 5"]
    assert all(not b["running"] for b in st["bots"])
    assert st["limits"] == {"min_lot": 0.01, "max_lot": 10.0}
    assert "Gold / Metals" in st["instruments"]
    assert registry.BOTS_FILE.exists()


def test_create_edit_delete():
    client = c()
    r = client.post("/api/bots", json={"name": "TEST BOT", "magic": 555, "instrument": "Forex",
                                       "description": "x", "lot_size": 0.05})
    assert r.status_code == 201
    bot = r.get_json()
    assert bot["lot_size"] == 0.05 and bot["running"] is False

    r = client.put(f"/api/bots/{bot['id']}", json={"name": "TEST BOT 2", "magic": 555,
                                                   "instrument": "Indices", "lot_size": 0.1})
    assert r.status_code == 200 and r.get_json()["name"] == "TEST BOT 2"

    assert client.delete(f"/api/bots/{bot['id']}").status_code == 200
    assert client.delete(f"/api/bots/{bot['id']}").status_code == 404


def test_saved_to_disk_and_reloaded():
    client = c()
    bot = client.post("/api/bots", json={"name": "PERSIST", "magic": 777}).get_json()
    registry.reload()                                   # simulate a server restart
    ids = [b["id"] for b in client.get("/api/bots").get_json()]
    assert bot["id"] in ids
    client.delete(f"/api/bots/{bot['id']}")


def test_validation():
    client = c()
    post = lambda **kw: client.post("/api/bots", json=kw).status_code
    assert post(name="", magic=1) == 400                          # name required
    assert post(name="A", magic="abc") == 400                     # magic must be number
    assert post(name="A", magic=1.5) == 400                       # whole number
    assert post(name="A", magic=-3) == 400                        # positive
    assert post(name="A", magic=27893) == 400                     # duplicate magic (GREAT M)
    assert post(name="A", magic=9001, instrument="Crypto") == 400 # unknown instrument
    assert post(name="A", magic=9001, lot_size=0) == 400
    assert post(name="A", magic=9001, lot_size=99) == 400
    assert post(name="A" * 41, magic=9001) == 400


def test_start_stop_and_locks():
    client = c()
    bid = "fury_flipper_2"
    assert client.post(f"/api/bots/{bid}/lot", json={"lot": 0.05}).get_json()["lot_size"] == 0.05
    assert client.post(f"/api/bots/{bid}/start").get_json()["running"] is True
    assert client.post(f"/api/bots/{bid}/lot", json={"lot": 0.2}).status_code == 409
    assert client.put(f"/api/bots/{bid}", json={"name": "X", "magic": 22002}).status_code == 409
    assert client.delete(f"/api/bots/{bid}").status_code == 409
    assert client.post(f"/api/bots/{bid}/stop").get_json()["running"] is False
    assert client.delete("/api/bots/nope").status_code == 404
    assert client.post("/api/bots/nope/start").status_code == 404


def test_start_all_stop_all_and_activity():
    client = c()
    n = len(client.get("/api/bots").get_json())
    assert client.post("/api/bots/start-all").get_json()["changed"] == n
    assert all(b["running"] for b in client.get("/api/bots").get_json())
    assert client.post("/api/bots/stop-all").get_json()["changed"] == n
    assert not any(b["running"] for b in client.get("/api/bots").get_json())
    msgs = [a["message"] for a in client.get("/api/state").get_json()["activity"]]
    assert any("Activated all bots" in m for m in msgs)


def test_stop_thread_really_ends():
    registry.start_bot("great_m")
    t = registry.get_bot("great_m")._thread
    registry.stop_bot("great_m")
    t.join(timeout=2)
    assert not t.is_alive()


if __name__ == "__main__":
    setup_module()
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn(); print("ok", name)
    finally:
        teardown_module()
        _TMP.cleanup()
