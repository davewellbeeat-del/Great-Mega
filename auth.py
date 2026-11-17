"""Password protection for the site.

* The password is set from the command line (py set_password.py), never from the website,
  so nobody can take over an unprotected site remotely.
* Only a hash is stored (data/auth.json), never the password itself.
* With NO password set, the site only answers requests from this computer.
* With a password set, every page and API call needs a login.
"""
import hashlib
import json
import os
import secrets
import threading
import time

from werkzeug.security import check_password_hash, generate_password_hash

import paths

AUTH_FILE = paths.DATA_DIR / "auth.json"
MIN_PASSWORD_LEN = 8
MAX_FAILS = 5
LOCK_SECONDS = 60

# Headers that prove a request came through a proxy or tunnel (Tailscale, Cloudflare, ngrok...)
PROXY_HEADERS = ("X-Forwarded-For", "X-Forwarded-Host", "X-Real-Ip", "Forwarded",
                 "Cf-Connecting-Ip", "Tailscale-User-Login")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}

_lock = threading.Lock()
_fails = {}          # ip -> [failed attempts, locked_until]


def _read() -> dict:
    try:
        data = json.loads(AUTH_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = AUTH_FILE.with_name(AUTH_FILE.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, AUTH_FILE)


def secret_key() -> str:
    with _lock:
        data = _read()
        if "secret_key" not in data:
            data["secret_key"] = secrets.token_hex(32)
            _write(data)
        return data["secret_key"]


def configured() -> bool:
    return bool(_read().get("password_hash"))


def set_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    with _lock:
        data = _read()
        data["password_hash"] = generate_password_hash(password)
        data.setdefault("secret_key", secrets.token_hex(32))
        _write(data)


def clear_password() -> None:
    with _lock:
        data = _read()
        data.pop("password_hash", None)
        _write(data)


def check_password(password: str) -> bool:
    pw_hash = _read().get("password_hash")
    return bool(pw_hash) and check_password_hash(pw_hash, password or "")


def _fingerprint() -> str:
    """Changes whenever the password changes, which signs everyone out."""
    return hashlib.sha256(_read().get("password_hash", "").encode()).hexdigest()[:16]


def log_in(session) -> None:
    session.clear()
    session["auth"] = _fingerprint()
    session.permanent = True


def log_out(session) -> None:
    session.clear()


def is_logged_in(session) -> bool:
    return configured() and session.get("auth") == _fingerprint()


# ---- brute-force protection ------------------------------------------------
def locked_for(ip: str) -> int:
    with _lock:
        rec = _fails.get(ip)
        if rec and rec[1] > time.time():
            return int(rec[1] - time.time()) + 1
        return 0


def record_failure(ip: str) -> None:
    with _lock:
        rec = _fails.setdefault(ip, [0, 0.0])
        if rec[1] and rec[1] <= time.time():
            rec[0], rec[1] = 0, 0.0               # an old lock expired: start counting again
        rec[0] += 1
        if rec[0] >= MAX_FAILS:
            rec[0], rec[1] = 0, time.time() + LOCK_SECONDS


def record_success(ip: str) -> None:
    with _lock:
        _fails.pop(ip, None)


# ---- "is this request from this very computer?" ------------------------------
def _host_name(host: str) -> str:
    host = (host or "").lower()
    return host.split("]")[0] + "]" if host.startswith("[") else host.split(":")[0]


def local_request(req) -> bool:
    if req.remote_addr not in ("127.0.0.1", "::1"):
        return False
    if any(h in req.headers for h in PROXY_HEADERS):
        return False
    return _host_name(req.host) in LOCAL_HOSTS
