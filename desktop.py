"""GREAT MEGA as a desktop app.

Starts the server in the background and opens it in its own window (no tabs, no address bar)
using Microsoft Edge or Google Chrome in "app mode". Both are standard on Windows, so nothing
extra needs installing. Closing the window stops the server and every bot.

    py desktop.py            open the app
    py desktop.py --check    start the server, test it, and exit (no window)
"""
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from werkzeug.serving import make_server

import paths
from app import app
from bots import registry

PORTS = range(8765, 8776)       # a fixed port keeps your saved theme and login between launches
WINDOW_SIZE = "1280,820"
logging.getLogger("werkzeug").setLevel(logging.ERROR)


# ---- server -----------------------------------------------------------------------
def our_server_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as r:
            return r.read().decode().strip() == "great-mega"
    except OSError:
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def start_server():
    """Returns (port, server_or_None). server is None when GREAT MEGA was already running."""
    for port in PORTS:
        if our_server_running(port):
            return port, None
        if port_free(port):
            server = make_server("127.0.0.1", port, app, threaded=True)
            threading.Thread(target=server.serve_forever, daemon=True, name="server").start()
            for _ in range(50):                      # wait until it answers
                if our_server_running(port):
                    return port, server
                time.sleep(0.1)
            server.shutdown()
    raise RuntimeError(f"No free port found between {PORTS.start} and {PORTS.stop - 1}.")


# ---- window -----------------------------------------------------------------------
def find_browser():
    candidates = []
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                           Path(base) / "Google/Chrome/Application/chrome.exe"]
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    return next((str(p) for p in candidates if p.exists()), None)


def open_window(url: str):
    """Open the app window. Returns the process to wait on, or None if we fell back to a normal tab."""
    browser = find_browser()
    if browser is None:
        webbrowser.open(url)
        return None
    profile = paths.DATA_DIR / "app-window"          # its own profile: remembers your theme and login
    profile.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen([
        browser, f"--app={url}", f"--user-data-dir={profile}",
        f"--window-size={WINDOW_SIZE}", "--no-first-run", "--no-default-browser-check",
    ])


# ---- main ---------------------------------------------------------------------------
def main() -> int:
    port, server = start_server()
    url = f"http://127.0.0.1:{port}/"

    if "--check" in sys.argv:
        print("READY", url, "(already running)" if server is None else "(started)")
        if server:
            server.shutdown()
        return 0

    proc = open_window(url)
    try:
        if server is not None:
            started = time.time()
            if proc is not None:
                proc.wait()                          # window closed -> shut everything down
            if proc is None or time.time() - started < 3:
                # no app window to wait on (or the browser handed the window to another process):
                # keep serving until Ctrl+C instead of stopping the bots by surprise
                print(f"GREAT MEGA is running at {url}\nPress Ctrl+C here to stop it.")
                while True:
                    time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:                       # only the instance that started the server stops it
            registry.stop_all()
            server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
