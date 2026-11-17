import os, sys, tempfile
from pathlib import Path

_TMP = tempfile.TemporaryDirectory()
os.environ["GREAT_MEGA_DATA"] = _TMP.name
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import auth
import mt5_link
from app import app
from fake_mt5 import FakeMT5
from mt5_link import Mt5Link


def setup_module():
    link = Mt5Link(loader=lambda: FakeMT5(), config_file=Path(_TMP.name) / "mt5.json")
    mt5_link.set_link(link)
    link.poll_once()
    return link


def client(header=True, remote="127.0.0.1"):
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = remote
    if header:
        c.environ_base["HTTP_X_REQUESTED_WITH"] = "GreatMega"
    return c


def test_state_contains_mt5_snapshot():
    setup_module()
    s = client().get("/api/state").get_json()
    assert s["mt5"]["status"] == "connected" and s["mt5"]["account"]["login"] == 12345678
    assert len(s["mt5"]["positions"]) == 2 and s["mt5"]["watchlist"][0] == "XAUUSD"


def test_history_endpoint():
    setup_module()
    h = client().get("/api/mt5/history?days=30").get_json()
    assert h["status"] == "connected" and [d["ticket"] for d in h["deals"]] == [7, 5, 3]
    assert client().get("/api/mt5/history?days=abc").status_code == 200       # junk falls back to 30
    assert client().get("/api/mt5/history?days=99999").get_json()["days"] == 365


def test_watchlist_endpoint_validation():
    link = setup_module()
    c = client()
    assert c.post("/api/mt5/watchlist", json={"symbols": ["GBPUSD", "EURUSD"]}).get_json()["watchlist"] == ["GBPUSD", "EURUSD"]
    for bad in ([], ["bad symbol"], ["x" * 30], None, "XAUUSD", [f"S{i}" for i in range(20)]):
        assert c.post("/api/mt5/watchlist", json={"symbols": bad}).status_code == 400, bad
    assert link.snapshot()["watchlist"] == ["GBPUSD", "EURUSD"]                # bad input changed nothing


def test_changes_need_the_security_header():
    setup_module()
    c = client(header=False)
    assert c.post("/api/mt5/watchlist", json={"symbols": ["XAUUSD"]}).status_code == 403
    assert c.post("/api/mt5/reconnect").status_code == 403
    assert c.get("/api/mt5/history").status_code == 200                        # reading is fine


def test_reconnect_endpoint():
    setup_module()
    r = client().post("/api/mt5/reconnect")
    assert r.status_code == 200 and r.get_json()["status"] == "connected"


def test_mt5_data_needs_login_when_password_set():
    setup_module()
    auth.set_password("a long password 1")
    try:
        anon = client(remote="192.168.1.50")
        assert anon.get("/api/state").status_code == 401
        assert anon.get("/api/mt5/history").status_code == 401
        assert anon.post("/api/mt5/watchlist", json={"symbols": ["XAUUSD"]}).status_code == 401
    finally:
        auth.clear_password()


def test_no_trading_endpoints_exist():
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert not [r for r in rules if any(w in r.lower() for w in ("order", "trade", "buy", "sell", "close-position"))], rules


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn(); print("ok", name)
    finally:
        _TMP.cleanup()
