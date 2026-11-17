# GREAT MEGA

Trading dashboard and bot control panel. Python (Flask) server, plain HTML/CSS/JS front end.
Use it in a browser, as a Windows app window, or as an installable app on your phone.

## Quick start (inside this folder, PowerShell)

    py -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    py app.py            # then open http://127.0.0.1:5000

After updating files, press Ctrl+F5 in the browser.

## Use it as an app

| Where | How |
|---|---|
| Laptop (app window) | Double-click **Start GREAT MEGA.bat**. Opens in its own window; closing it stops the server and all bots. |
| Laptop (single .exe) | Double-click **build_windows_app.bat** once; your app appears at `dist\GreatMega.exe`. |
| Phone | See **PHONE_SETUP.md** (home Wi-Fi, or anywhere via Tailscale). Set a password first. |

The .exe keeps its data (bots, password) in `%APPDATA%\GreatMega\data`, separate from this folder.

## Connect MetaTrader 5 (read-only)

See **MT5_SETUP.md**. In short: log in to MT5, `pip install MetaTrader5`, run `py mt5_check.py`,
then start the site. The dashboard then shows your real balance, equity, positions, prices and history.
It cannot trade.

## Security

- No password set: the site only answers this computer.
- Password set (Settings > Security): every page and API call needs a login. 5 wrong tries lock login for 60 seconds.
- Changing the password signs out every other device. Forgot it? Run `py set_password.py`.
- Buttons only work from pages of this site (a hidden header blocks other websites from pressing them).

## Change the colours

Click **Theme** (top right): 12 accent colours, a custom colour picker and 6 backgrounds.
Defaults are at the top of static/css/style.css.

## Folder layout

    app.py                  server and API
    desktop.py              opens the app window on Windows
    auth.py, paths.py       password protection; where data lives
    set_password.py         set/remove the password from the command line
    mt5_link.py             read-only MetaTrader 5 link;  mt5_check.py tests the connection
    bots/registry.py        bots: add / edit / delete / start / stop / lot size (+ how to add real logic)
    templates/, static/     the pages, styles, scripts, icons, app manifest, service worker
    make_icons.py           regenerates the icons (needs: pip install pillow)
    tests/run_all.py        run all tests:  py tests/run_all.py

## Important

- With MT5 connected the dashboard shows real figures; without it, it shows a dash. Nothing is made up.
- Bots are placeholders: they can be activated and stopped, but place NO trades yet.
- Bots always start inactive after a restart. Lot sizes are limited to 0.01 - 10.0 (MAX_LOT).
- Bots cannot be edited, deleted or have their lot size changed while active.
