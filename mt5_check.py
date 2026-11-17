"""Check your MetaTrader 5 connection. READ-ONLY: it never trades.

    py mt5_check.py

Run this with MetaTrader 5 open and logged in. It prints what GREAT MEGA will be able to see,
and tells you what to fix if something is wrong.
"""
import platform
import struct
import sys

print(f"Python {platform.python_version()} ({struct.calcsize('P') * 8}-bit) on {platform.system()}")
if platform.system() != "Windows":
    print("-> The MetaTrader5 package only works on Windows.")
if struct.calcsize("P") * 8 != 64:
    print("-> The MetaTrader5 package needs 64-bit Python.")

try:
    import MetaTrader5 as mt5
except ImportError:
    print("\nFAIL: the MetaTrader5 package is not installed.")
    print("Fix:  pip install MetaTrader5      (run it inside your .venv)")
    print("If pip says no matching distribution, your Python version is probably too new:")
    print("install Python 3.12 (64-bit) and recreate the .venv with it.")
    sys.exit(1)
print(f"MetaTrader5 package {getattr(mt5, '__version__', '?')} found")

if not mt5.initialize():
    print(f"\nFAIL: could not connect to the MetaTrader 5 program: {mt5.last_error()}")
    print("Fix: open MetaTrader 5, log in to your account, wait for the connection icon (bottom right)")
    print("to show data, then run this again. If you have several MT5 programs installed, put the full")
    print('path of the right terminal64.exe in data/mt5.json like:  {"path": "C:/Program Files/MetaTrader 5/terminal64.exe"}')
    sys.exit(1)

try:
    term = mt5.terminal_info()
    print(f"\nTerminal : {term.name if term else '?'}  connected to broker: {getattr(term, 'connected', '?')}")
    print(f"Path     : {getattr(term, 'path', '?')}")

    acc = mt5.account_info()
    if acc is None:
        print("\nFAIL: MetaTrader 5 is open but no account is logged in.")
        sys.exit(1)
    mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(acc.trade_mode, "?")
    print(f"\nAccount  : {acc.login}  ({mode})  {acc.name}")
    print(f"Broker   : {acc.company}  server {acc.server}")
    print(f"Balance  : {acc.balance:.2f} {acc.currency}   Equity: {acc.equity:.2f}   Open profit: {acc.profit:.2f}")
    if mode == "REAL":
        print("NOTE     : this is a REAL account. GREAT MEGA only reads it; it cannot trade.")

    print("\nSymbols (name you type -> name at your broker):")
    for wanted in ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY"):
        info = mt5.symbol_info(wanted)
        name = info.name if info else None
        if name is None:
            found = sorted((s.name for s in (mt5.symbols_get(group=f"*{wanted}*") or [])), key=len)
            name = found[0] if found else None
        if name is None:
            print(f"  {wanted:8} -> NOT FOUND (use your broker's name in Settings > MetaTrader 5)")
            continue
        mt5.symbol_select(name, True)
        tick = mt5.symbol_info_tick(name)
        print(f"  {wanted:8} -> {name:12} bid {tick.bid if tick else 'no price yet'}")

    positions = mt5.positions_get() or []
    print(f"\nOpen positions: {len(positions)}")
    for p in positions[:5]:
        print(f"  #{p.ticket} {p.symbol} {'BUY' if p.type == 0 else 'SELL'} {p.volume} lots, profit {p.profit:.2f}, magic {p.magic}")

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    deals = mt5.history_deals_get(now - timedelta(days=7), now + timedelta(days=1)) or []
    print(f"Deals in the last 7 days: {len(deals)}")
    print("\nOK: GREAT MEGA can read your account. Start the site and open the Dashboard.")
finally:
    mt5.shutdown()
