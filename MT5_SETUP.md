# Connecting GREAT MEGA to MetaTrader 5 (read-only)

GREAT MEGA reads your account from the MetaTrader 5 program on this computer: balance, equity,
open positions, live prices and closed trades. **It cannot place, change or close trades.**
(The code has no trading functions, and a test fails if one is ever added.)

## What you need

- Windows, with MetaTrader 5 installed (from your broker) and **logged in**. Use a **demo account** first.
- **64-bit Python** (the project's `.venv`). If the install step below says "no matching distribution",
  your Python is probably too new for the package: install Python 3.12 (64-bit) and recreate `.venv` with it.

## Steps

1. Open MetaTrader 5 and log in. Wait until prices are moving (connection icon, bottom right).
2. In the VS Code terminal (with `.venv` active):

       pip install MetaTrader5

3. Check the connection (this never trades):

       py mt5_check.py

   You should see your account number, DEMO or REAL, balance, your symbols and any open positions.
   If something is wrong, it tells you what to fix.
4. Start GREAT MEGA (`py app.py` or **Start GREAT MEGA.bat**). The top bar shows
   **MT5 connected - DEMO** and the Dashboard fills with your real figures.

## Symbol names

Brokers rename symbols (`XAUUSDm`, `EURUSD.r`, `GOLD`...). GREAT MEGA tries to match what you type
automatically. To change the list: **Settings > MetaTrader 5 > Market Watch symbols** (up to 12).
If a symbol shows "Not found at your broker", type the exact name from MT5's Market Watch window.

## What you will see

| Where | What |
|---|---|
| Top bar | MT5 connected (DEMO or REAL), or what is wrong |
| Dashboard | Balance, equity, open profit, closed profit for the latest trading day, live prices, open positions (matched to your bots by magic number) |
| My Accounts | Account details of whichever account MT5 is logged in to |
| Trade History | Closed trades from the last 30 days (times are your broker's server time) |
| Settings | Connection details, symbol list, **Reconnect** button |

If the account is a **REAL** account, a gold warning banner is shown on the Dashboard.
To use a different account, log in to it inside MT5; GREAT MEGA follows whichever account MT5 shows.

## Troubleshooting

| Message | Fix |
|---|---|
| "MetaTrader5 Python package is not installed" | `pip install MetaTrader5` inside the `.venv`, then press **Reconnect** in Settings |
| "Could not reach MetaTrader 5" | Open MT5 and log in. If MT5 runs "as administrator", run VS Code/Python as administrator too (they must match) |
| "no account is logged in" / "not connected to your broker" | Log in inside MT5 and wait for the connection icon |
| Wrong terminal opens (several MT5s installed) | Create `data/mt5.json` with `{"path": "C:/Program Files/Your Broker MT5/terminal64.exe"}` |
| Prices missing for a symbol | Use your broker's exact symbol name (see above) |

The link refreshes every 2 seconds and reconnects by itself if MT5 is closed and reopened.
Your phone sees the same data, through the website on your laptop.

## Not yet included

Trading from the website (placing or closing orders, running bots through MT5). That is the next
stage, and should start on a demo account with a daily-loss limit and a kill switch.
