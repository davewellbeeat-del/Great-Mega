"""Read-only link to MetaTrader 5.

GREAT MEGA uses the official `MetaTrader5` Python package to READ from the MT5 program that is
open and logged in on this computer: account figures, open positions, prices and deal history.

This module can NOT trade. It only calls MT5's read functions (initialize, account_info,
positions_get, symbol_info_tick, history_deals_get and similar). tests/test_mt5.py fails if a
trading call is ever added.

A background thread refreshes a snapshot every couple of seconds; web requests only read that
snapshot, so the website never waits on MT5 and MT5 is only ever used by one thread at a time.
"""
import atexit
import importlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import paths

CONFIG_FILE = paths.DATA_DIR / "mt5.json"
DEFAULT_WATCHLIST = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
MAX_WATCH = 12
SYMBOL_RE = re.compile(r"^[A-Za-z0-9._#\-]{1,20}$")

POLL_CONNECTED = 2.0      # seconds between refreshes while connected
POLL_RETRY = 10.0         # seconds between connection attempts while not connected
HISTORY_TTL = 10.0
MAX_POSITIONS = 50
MAX_DEALS = 200


def _default_loader():
    import MetaTrader5 as mt5          # raises ImportError when the package is not installed
    return mt5


def _utc(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _stamp(ts: float) -> str:
    return _utc(ts).strftime("%Y-%m-%d %H:%M")


def clean_watchlist(symbols) -> list:
    """Validate a list of symbol names typed by the user. Raises ValueError with a clear message."""
    if not isinstance(symbols, (list, tuple)):
        raise ValueError("Symbols must be a list.")
    out, seen = [], set()
    for raw in symbols:
        name = str(raw).strip()
        if not name:
            continue
        if not SYMBOL_RE.match(name):
            raise ValueError(f"'{name}' is not a valid symbol name (letters, numbers and . _ # - only).")
        if name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    if not out:
        raise ValueError("Enter at least one symbol.")
    if len(out) > MAX_WATCH:
        raise ValueError(f"Please use {MAX_WATCH} symbols or fewer.")
    return out


class Mt5Link:
    def __init__(self, loader=None, config_file=None):
        self._loader = loader or _default_loader
        self._config_file = Path(config_file) if config_file else CONFIG_FILE
        self._mt5 = None
        self._io = threading.RLock()            # only one thread talks to MT5 at a time
        self._start_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._connected = False
        self._resolved = {}                     # name typed -> name at the broker
        self._server_now = None
        self._history_cache = {}
        cfg = self._load_config()
        self._watchlist = cfg["watchlist"]
        self._path = cfg["path"]
        self._snap = self._empty("starting", "Connecting to MetaTrader 5...")

    # ---------------------------------------------------------------- config
    def _load_config(self) -> dict:
        cfg = {"watchlist": list(DEFAULT_WATCHLIST), "path": None}
        try:
            data = json.loads(self._config_file.read_text())
            if isinstance(data, dict):
                try:
                    cfg["watchlist"] = clean_watchlist(data.get("watchlist"))
                except ValueError:
                    pass
                if isinstance(data.get("path"), str) and data["path"].strip():
                    cfg["path"] = data["path"].strip()
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return cfg

    def _save_config(self) -> None:
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._config_file.with_name(self._config_file.name + ".tmp")
        tmp.write_text(json.dumps({"watchlist": self._watchlist, "path": self._path}, indent=2))
        os.replace(tmp, self._config_file)

    def set_watchlist(self, symbols) -> list:
        names = clean_watchlist(symbols)
        with self._io:
            self._watchlist = names
            self._resolved.clear()
            self._save_config()
        return list(names)

    # ---------------------------------------------------------------- snapshots
    @staticmethod
    def _empty(status: str, message: str) -> dict:
        return {"status": status, "message": message, "account": None, "today_profit": None,
                "positions": [], "market": [], "updated_at": time.time()}

    def snapshot(self) -> dict:
        snap = dict(self._snap)
        snap["watchlist"] = list(self._watchlist)
        return snap

    # ---------------------------------------------------------------- thread
    def ensure_started(self) -> None:
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="mt5-link")
            self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as exc:            # nothing may ever kill the polling thread
                with self._io:
                    self._disconnect(f"Unexpected error: {exc}")
            self._stop.wait(POLL_CONNECTED if self._connected else POLL_RETRY)

    def close(self) -> None:
        self._stop.set()
        with self._io:
            self._shutdown_quietly()
            self._connected = False

    # ---------------------------------------------------------------- connection
    def poll_once(self) -> None:
        """One refresh cycle (the thread calls this; tests call it directly)."""
        with self._io:
            if self._mt5 is None:
                importlib.invalidate_caches()   # lets a freshly installed package be found without a restart
                try:
                    self._mt5 = self._loader()
                except ImportError:
                    self._mt5 = None
                if self._mt5 is None:
                    self._snap = self._empty(
                        "not_installed",
                        "The MetaTrader5 Python package is not installed. In the VS Code terminal run: pip install MetaTrader5")
                    return
            if not self._connected and not self._connect():
                return
            try:
                self._snap = self._build()
            except Exception as exc:
                self._disconnect(f"Lost the connection to MetaTrader 5 ({exc}). Retrying...")

    def _connect(self) -> bool:
        mt5 = self._mt5
        kwargs = {"path": self._path} if self._path else {}
        try:
            ok = mt5.initialize(**kwargs)
            err = None if ok else mt5.last_error()
        except Exception as exc:
            ok, err = False, exc
        if not ok:
            self._snap = self._empty(
                "disconnected",
                f"Could not reach MetaTrader 5 ({err}). Open the MetaTrader 5 program and log in to your account.")
            return False

        terminal = mt5.terminal_info()
        if terminal is not None and not getattr(terminal, "connected", True):
            self._disconnect("MetaTrader 5 is open but not connected to your broker. "
                             "Check the connection indicator at the bottom right of MT5.")
            return False
        if mt5.account_info() is None:
            self._disconnect("MetaTrader 5 is open but no account is logged in. Log in to your account in MT5.")
            return False

        self._connected = True
        self._resolved.clear()
        self.__dict__.pop("_digits_cache", None)
        return True

    def _shutdown_quietly(self) -> None:
        try:
            if self._mt5 is not None:
                self._mt5.shutdown()
        except Exception:
            pass

    def _disconnect(self, message: str) -> None:
        self._shutdown_quietly()
        self._connected = False
        self._snap = self._empty("disconnected", message)

    def reconnect(self) -> dict:
        """Drop the connection and try again right now (Settings > Reconnect)."""
        with self._io:
            self._shutdown_quietly()
            self._connected = False
            self._mt5 = None
            self.poll_once()
        return self.snapshot()

    # ---------------------------------------------------------------- reading
    def _resolve(self, wanted: str):
        """Brokers rename symbols (XAUUSDm, EURUSD.r, GOLD...). Find the real name."""
        if wanted in self._resolved:
            return self._resolved[wanted]
        mt5 = self._mt5
        name = None
        info = mt5.symbol_info(wanted)
        if info is not None:
            name = info.name
        else:
            found = mt5.symbols_get(group=f"*{wanted}*") or []
            names = sorted((s.name for s in found),
                           key=lambda n: (not n.upper().startswith(wanted.upper()), len(n), n))
            name = names[0] if names else None
        if name:
            try:
                mt5.symbol_select(name, True)
            except Exception:
                pass
        self._resolved[wanted] = name
        return name

    def _market(self):
        mt5, rows, newest_tick = self._mt5, [], None
        for wanted in self._watchlist:
            name = self._resolve(wanted)
            if not name:
                rows.append({"requested": wanted, "symbol": None, "error": "Not found at your broker"})
                continue
            tick = mt5.symbol_info_tick(name)
            if tick is None or not getattr(tick, "bid", 0):
                rows.append({"requested": wanted, "symbol": name, "error": "No price yet"})
                continue
            info = mt5.symbol_info(name)
            day_open = None
            rates = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_D1, 0, 1)
            if rates is not None and len(rates):
                day_open = float(rates[0]["open"])
            change = (tick.bid - day_open) / day_open * 100 if day_open else None
            rows.append({"requested": wanted, "symbol": name, "price": float(tick.bid),
                         "ask": float(tick.ask), "digits": int(info.digits) if info else 5,
                         "change_pct": change})
            newest_tick = max(newest_tick or 0, int(tick.time))
        return rows, newest_tick

    def _digits(self, symbol):
        """Decimal places of a symbol (None if unknown), cached for the connection."""
        cache = self.__dict__.setdefault("_digits_cache", {})
        if symbol not in cache:
            info = self._mt5.symbol_info(symbol)
            cache[symbol] = int(info.digits) if info is not None else None
        return cache[symbol]

    def _mode_name(self, mode) -> str:
        mt5 = self._mt5
        if mode == getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0):
            return "demo"
        if mode == getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", 2):
            return "real"
        if mode == getattr(mt5, "ACCOUNT_TRADE_MODE_CONTEST", 1):
            return "contest"
        return "unknown"

    def _is_trade_deal(self, deal) -> bool:
        mt5 = self._mt5
        return deal.type in (getattr(mt5, "DEAL_TYPE_BUY", 0), getattr(mt5, "DEAL_TYPE_SELL", 1))

    def _build(self) -> dict:
        mt5 = self._mt5
        acc = mt5.account_info()
        if acc is None:
            raise RuntimeError("no account is logged in")

        market, newest_tick = self._market()
        # MT5 timestamps are in the broker's server time. "Today" means the server's current day.
        server_now = newest_tick or int(time.time())
        self._server_now = server_now
        day_start = server_now - server_now % 86400

        positions = []
        buy = getattr(mt5, "POSITION_TYPE_BUY", 0)
        for p in sorted(mt5.positions_get() or [], key=lambda p: p.ticket)[:MAX_POSITIONS]:
            positions.append({
                "ticket": int(p.ticket), "symbol": p.symbol, "type": "buy" if p.type == buy else "sell",
                "volume": float(p.volume), "price_open": float(p.price_open),
                "price_current": float(p.price_current), "profit": float(p.profit),
                "swap": float(p.swap), "magic": int(p.magic), "comment": p.comment or "",
                "digits": self._digits(p.symbol),
            })

        today = None
        deals = mt5.history_deals_get(_utc(day_start - 86400), _utc(server_now + 86400))
        if deals is not None:
            today = sum(d.profit + d.commission + d.swap
                        for d in deals if self._is_trade_deal(d) and d.time >= day_start)

        mode = self._mode_name(acc.trade_mode)
        return {
            "status": "connected", "message": "",
            "account": {
                "login": int(acc.login), "name": acc.name, "server": acc.server, "company": acc.company,
                "currency": acc.currency, "leverage": int(acc.leverage),
                "balance": float(acc.balance), "equity": float(acc.equity), "profit": float(acc.profit),
                "margin": float(acc.margin), "free_margin": float(acc.margin_free),
                "mode": mode, "is_real": mode == "real",
            },
            "today_profit": today,
            "positions": positions,
            "market": market,
            "updated_at": time.time(),
        }

    def history(self, days: int = 30) -> dict:
        """Closed trades for the Trade History page (newest first)."""
        days = max(1, min(int(days), 365))
        with self._io:
            if not self._connected:
                return {"status": self._snap["status"], "message": self._snap["message"],
                        "deals": [], "total": 0.0, "days": days}
            cached = self._history_cache.get(days)
            if cached and time.time() - cached[0] < HISTORY_TTL:
                return cached[1]

            mt5 = self._mt5
            now = self._server_now or int(time.time())
            try:
                raw = mt5.history_deals_get(_utc(now - days * 86400), _utc(now + 86400))
            except Exception as exc:
                return {"status": "connected", "message": f"Could not read history: {exc}",
                        "deals": [], "total": 0.0, "days": days}

            closing = {getattr(mt5, "DEAL_ENTRY_OUT", 1), getattr(mt5, "DEAL_ENTRY_INOUT", 2),
                       getattr(mt5, "DEAL_ENTRY_OUT_BY", 3)}
            buy = getattr(mt5, "DEAL_TYPE_BUY", 0)
            rows = []
            for d in raw or []:
                if not self._is_trade_deal(d) or d.entry not in closing:
                    continue
                direction = "buy" if d.type == buy else "sell"
                if d.entry != getattr(mt5, "DEAL_ENTRY_INOUT", 2):     # a closing SELL deal ends a BUY trade
                    direction = "sell" if direction == "buy" else "buy"
                rows.append({
                    "time": _stamp(d.time), "ts": int(d.time), "ticket": int(d.ticket), "symbol": d.symbol,
                    "type": direction, "volume": float(d.volume), "price": float(d.price),
                    "profit": float(d.profit), "commission": float(d.commission), "swap": float(d.swap),
                    "net": float(d.profit + d.commission + d.swap), "magic": int(d.magic),
                    "digits": self._digits(d.symbol),
                })
            rows.sort(key=lambda r: r["ts"], reverse=True)
            result = {"status": "connected", "message": "", "days": days,
                      "total": sum(r["net"] for r in rows), "deals": rows[:MAX_DEALS]}
            self._history_cache[days] = (time.time(), result)
            return result


# ---- one shared link for the whole app --------------------------------------------------------
_link = None
_link_lock = threading.Lock()


def get_link() -> Mt5Link:
    global _link
    with _link_lock:
        if _link is None:
            _link = Mt5Link()
            atexit.register(_link.close)
        return _link


def set_link(link) -> None:
    """Used by tests to plug in a simulated MT5."""
    global _link
    with _link_lock:
        _link = link
