"""A stand-in for the MetaTrader5 package so the link can be tested without MT5.

It mimics the shapes the real package returns (named tuples with the same field names) and
records every function that gets called, so tests can prove the link never trades.
"""
import fnmatch
from collections import namedtuple

Account = namedtuple("Account", "login trade_mode name server currency leverage balance profit equity margin margin_free company")
Position = namedtuple("Position", "ticket time type magic volume price_open sl tp price_current swap profit symbol comment")
Deal = namedtuple("Deal", "ticket time type entry magic volume price commission swap profit symbol comment")
Tick = namedtuple("Tick", "time bid ask")
SymInfo = namedtuple("SymInfo", "name digits")
Sym = namedtuple("Sym", "name")
Terminal = namedtuple("Terminal", "connected path trade_allowed")

DAY = 86400
NOW = 1_700_000_000 - (1_700_000_000 % DAY) + 15 * 3600      # 15:00 on some server day
TODAY = NOW - NOW % DAY


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_CONTEST, ACCOUNT_TRADE_MODE_REAL = 0, 1, 2
    POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
    DEAL_TYPE_BUY, DEAL_TYPE_SELL, DEAL_TYPE_BALANCE = 0, 1, 2
    DEAL_ENTRY_IN, DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT, DEAL_ENTRY_OUT_BY = 0, 1, 2, 3
    TIMEFRAME_D1 = 16408

    def __init__(self):
        self.calls = []
        self.init_ok = True
        self.last_err = (-10005, "IPC timeout")
        self.terminal_connected = True
        self.logged_in = True
        self.explode_on_account = False
        self.mode = 0
        self.symbols = {                                  # broker names differ from what people type
            "XAUUSDm": dict(bid=2650.40, ask=2650.70, digits=2, day_open=2628.80),
            "EURUSD": dict(bid=1.08420, ask=1.08430, digits=5, day_open=1.08160),
            "GBPUSD": dict(bid=1.29140, ask=1.29152, digits=5, day_open=1.29310),
        }
        self.positions = [
            Position(11, NOW - 600, 0, 22002, 0.10, 2640.0, 0, 0, 2650.4, -0.5, 104.0, "XAUUSDm", "bot"),
            Position(12, NOW - 300, 1, 0, 0.50, 1.0850, 0, 0, 1.0842, 0.0, 40.0, "EURUSD", ""),
        ]
        self.deals = [
            Deal(1, TODAY - DAY - 3600, 2, 0, 0, 0.0, 0, 0, 0, 5000.0, "", "deposit"),             # balance op, yesterday
            Deal(2, TODAY - DAY + 100, 0, 0, 22002, 0.1, 2600.0, -0.7, 0, 0.0, "XAUUSDm", ""),     # yesterday IN
            Deal(3, TODAY - DAY + 900, 1, 1, 22002, 0.1, 2610.0, 0.0, -0.2, 100.0, "XAUUSDm", ""),  # yesterday OUT (closes a buy)
            Deal(4, TODAY + 1000, 0, 0, 22003, 0.2, 1.0800, -1.4, 0, 0.0, "EURUSD", ""),            # today IN (commission only)
            Deal(5, TODAY + 5000, 1, 1, 22003, 0.2, 1.0830, 0.0, -0.1, 60.0, "EURUSD", ""),         # today OUT (closes a buy)
            Deal(6, TODAY + 6000, 1, 0, 0, 0.1, 2640.0, -0.7, 0, 0.0, "XAUUSDm", ""),              # today IN (sell)
            Deal(7, TODAY + 9000, 0, 1, 0, 0.1, 2630.0, 0.0, 0.0, -25.0, "XAUUSDm", ""),            # today OUT (closes a sell, loss)
            Deal(8, TODAY + 9500, 2, 0, 0, 0.0, 0, 0, 0, 1000.0, "", "top-up"),                     # balance op today: ignored
        ]

    # --- every public call is recorded -------------------------------------------------
    def _rec(self, name):
        self.calls.append(name)

    def initialize(self, **kwargs):
        self._rec("initialize")
        self.init_kwargs = kwargs
        return self.init_ok

    def shutdown(self):
        self._rec("shutdown")

    def last_error(self):
        self._rec("last_error")
        return self.last_err

    def terminal_info(self):
        self._rec("terminal_info")
        return Terminal(self.terminal_connected, "C:/MT5", True)

    def account_info(self):
        self._rec("account_info")
        if self.explode_on_account:
            raise RuntimeError("terminal went away")
        if not self.logged_in:
            return None
        return Account(12345678, self.mode, "Test User", "Broker-Demo", "USD", 500, 5240.0, 144.0, 5384.0, 120.0, 5264.0, "Test Broker Ltd")

    def symbols_get(self, group=None):
        self._rec("symbols_get")
        names = list(self.symbols)
        if group:
            names = [n for n in names if fnmatch.fnmatch(n.upper(), group.upper())]
        return [Sym(n) for n in names]

    def symbol_info(self, name):
        self._rec("symbol_info")
        s = self.symbols.get(name)
        return SymInfo(name, s["digits"]) if s else None

    def symbol_select(self, name, enable):
        self._rec("symbol_select")
        return name in self.symbols

    def symbol_info_tick(self, name):
        self._rec("symbol_info_tick")
        s = self.symbols.get(name)
        return Tick(NOW, s["bid"], s["ask"]) if s else None

    def copy_rates_from_pos(self, name, timeframe, start, count):
        self._rec("copy_rates_from_pos")
        s = self.symbols.get(name)
        return [{"open": s["day_open"]}] if s else None

    def positions_get(self):
        self._rec("positions_get")
        return list(self.positions)

    def history_deals_get(self, date_from, date_to):
        self._rec("history_deals_get")
        lo, hi = date_from.timestamp(), date_to.timestamp()
        return [d for d in self.deals if lo <= d.time <= hi]
