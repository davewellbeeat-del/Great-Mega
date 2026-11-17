import json, os, re, sys, tempfile
from pathlib import Path

_TMP = tempfile.TemporaryDirectory()
os.environ["GREAT_MEGA_DATA"] = _TMP.name
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mt5_link
from mt5_link import Mt5Link, clean_watchlist
from fake_mt5 import FakeMT5, TODAY


def make(fake=None, **kw):
    fake = fake or FakeMT5()
    cfg = Path(_TMP.name) / "mt5_test.json"
    cfg.unlink(missing_ok=True)
    link = Mt5Link(loader=lambda: fake, config_file=cfg, **kw)
    return link, fake


def near(a, b, tol=1e-6):
    return abs(a - b) < tol


# ---------------------------------------------------------------- the safety promise
def test_link_is_read_only():
    src = (ROOT / "mt5_link.py").read_text()
    code = re.sub(r'""".*?"""', "", src, flags=re.S)            # ignore the explanatory docstrings
    assert not re.search(r"order_|positions_close|\.buy\(|\.sell\(|Request|trade_request", code), \
        "mt5_link.py must never call a trading function"


def test_only_read_functions_are_called():
    link, fake = make()
    link.poll_once()
    link.history(30)
    allowed = {"initialize", "shutdown", "last_error", "terminal_info", "account_info", "symbols_get",
               "symbol_info", "symbol_select", "symbol_info_tick", "copy_rates_from_pos",
               "positions_get", "history_deals_get"}
    assert set(fake.calls) <= allowed, set(fake.calls) - allowed


# ---------------------------------------------------------------- snapshot content
def test_connected_snapshot():
    link, fake = make()
    link.poll_once()
    s = link.snapshot()
    assert s["status"] == "connected"
    a = s["account"]
    assert (a["login"], a["currency"], a["mode"], a["is_real"]) == (12345678, "USD", "demo", False)
    assert near(a["balance"], 5240.0) and near(a["equity"], 5384.0) and near(a["profit"], 144.0)
    assert [p["type"] for p in s["positions"]] == ["buy", "sell"]
    assert s["positions"][0]["magic"] == 22002 and s["positions"][0]["symbol"] == "XAUUSDm"


def test_symbols_are_resolved_to_broker_names_and_change_is_computed():
    link, fake = make()
    link.poll_once()
    rows = {r["requested"]: r for r in link.snapshot()["market"]}
    assert rows["XAUUSD"]["symbol"] == "XAUUSDm"                       # XAUUSD -> XAUUSDm
    assert near(rows["XAUUSD"]["change_pct"], (2650.40 - 2628.80) / 2628.80 * 100, 1e-9)
    assert rows["GBPUSD"]["change_pct"] < 0                            # fell today
    assert rows["USDJPY"]["symbol"] is None and "Not found" in rows["USDJPY"]["error"]


def test_todays_profit_uses_server_day_and_ignores_balance_operations():
    link, fake = make()
    link.poll_once()
    # today: (0-1.4-0) + (60-0.1) + (0-0.7) + (-25) = 32.8 ; yesterday's deals and the deposits are excluded
    assert near(link.snapshot()["today_profit"], -1.4 + 59.9 - 0.7 - 25.0, 1e-9)


def test_positions_and_history_carry_symbol_digits():
    link, fake = make()
    link.poll_once()
    pos = {p["symbol"]: p for p in link.snapshot()["positions"]}
    assert pos["EURUSD"]["digits"] == 5 and pos["XAUUSDm"]["digits"] == 2
    assert {d["digits"] for d in link.history(30)["deals"]} == {5, 2}


def test_real_account_is_flagged():
    fake = FakeMT5(); fake.mode = 2
    link, _ = make(fake)
    link.poll_once()
    a = link.snapshot()["account"]
    assert a["mode"] == "real" and a["is_real"] is True


# ---------------------------------------------------------------- history
def test_history_lists_closed_trades_newest_first_with_trade_direction():
    link, fake = make()
    link.poll_once()
    h = link.history(30)
    assert h["status"] == "connected"
    assert [d["ticket"] for d in h["deals"]] == [7, 5, 3]              # only closing deals, newest first
    assert [d["type"] for d in h["deals"]] == ["sell", "buy", "buy"]   # direction of the TRADE, not the closing deal
    assert near(h["deals"][0]["net"], -25.0) and near(h["total"], -25.0 + 59.9 + 99.8, 1e-9)
    assert h["deals"][0]["time"].count("-") == 2 and ":" in h["deals"][0]["time"]


def test_history_window_respects_days():
    link, fake = make()
    link.poll_once()
    assert [d["ticket"] for d in link.history(1)["deals"]] == [7, 5]   # last day only (yesterday's close is older)


def test_history_is_cached_briefly():
    link, fake = make()
    link.poll_once()
    link.history(30); n = fake.calls.count("history_deals_get")
    link.history(30)
    assert fake.calls.count("history_deals_get") == n


# ---------------------------------------------------------------- failures and recovery
def test_package_not_installed():
    def boom():
        raise ImportError("no module")
    link = Mt5Link(loader=boom, config_file=Path(_TMP.name) / "x.json")
    link.poll_once()
    s = link.snapshot()
    assert s["status"] == "not_installed" and "pip install MetaTrader5" in s["message"]
    assert link.history()["deals"] == []


def test_terminal_not_running_then_recovers():
    fake = FakeMT5(); fake.init_ok = False
    link, _ = make(fake)
    link.poll_once()
    s = link.snapshot()
    assert s["status"] == "disconnected" and "IPC timeout" in s["message"] and "log in" in s["message"]
    fake.init_ok = True
    link.poll_once()
    assert link.snapshot()["status"] == "connected"


def test_not_logged_in_and_broker_offline_messages():
    fake = FakeMT5(); fake.logged_in = False
    link, _ = make(fake)
    link.poll_once()
    assert "no account is logged in" in link.snapshot()["message"]

    fake2 = FakeMT5(); fake2.terminal_connected = False
    link2, _ = make(fake2)
    link2.poll_once()
    assert "not connected to your broker" in link2.snapshot()["message"]


def test_connection_lost_mid_session_then_recovers():
    link, fake = make()
    link.poll_once()
    assert link.snapshot()["status"] == "connected"
    fake.explode_on_account = True
    link.poll_once()
    s = link.snapshot()
    assert s["status"] == "disconnected" and "terminal went away" in s["message"] and s["account"] is None
    assert "shutdown" in fake.calls
    fake.explode_on_account = False
    link.poll_once()
    assert link.snapshot()["status"] == "connected"


def test_reconnect_reconnects():
    link, fake = make()
    link.poll_once()
    snap = link.reconnect()
    assert snap["status"] == "connected" and fake.calls.count("initialize") == 2


def test_custom_terminal_path_is_used():
    cfg = Path(_TMP.name) / "mt5_path.json"
    cfg.write_text(json.dumps({"path": "C:/Broker MT5/terminal64.exe"}))
    fake = FakeMT5()
    link = Mt5Link(loader=lambda: fake, config_file=cfg)
    link.poll_once()
    assert fake.init_kwargs == {"path": "C:/Broker MT5/terminal64.exe"}


# ---------------------------------------------------------------- watchlist
def test_watchlist_validation_and_persistence():
    assert clean_watchlist(["XAUUSD", " eurusd ", "XAUUSD"]) == ["XAUUSD", "eurusd"]       # trimmed, de-duplicated
    for bad in ([], [""], ["bad symbol"], ["x;drop"], ["A"] * 1 + ["B" * 21], [f"S{i}" for i in range(13)], "XAUUSD", None):
        try:
            clean_watchlist(bad)
        except ValueError:
            continue
        raise AssertionError(f"should have rejected {bad!r}")

    link, fake = make()
    link.poll_once()
    link.set_watchlist(["GBPUSD", "EURUSD"])
    link.poll_once()
    assert [r["requested"] for r in link.snapshot()["market"]] == ["GBPUSD", "EURUSD"]
    again = Mt5Link(loader=lambda: fake, config_file=Path(_TMP.name) / "mt5_test.json")      # reload from disk
    assert again.snapshot()["watchlist"] == ["GBPUSD", "EURUSD"]


def test_polling_thread_runs_and_stops():
    import time
    link, fake = make()
    link.ensure_started()
    for _ in range(50):
        if link.snapshot()["status"] == "connected":
            break
        time.sleep(0.05)
    assert link.snapshot()["status"] == "connected"
    link.close()
    assert "shutdown" in fake.calls


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn(); print("ok", name)
    finally:
        _TMP.cleanup()
