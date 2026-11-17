import argparse
import socket
from datetime import timedelta

from flask import (Flask, Response, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)

import auth
import mt5_link
import paths
from bots import registry

app = Flask(
    __name__,
    template_folder=str(paths.RESOURCE_DIR / "templates"),
    static_folder=str(paths.RESOURCE_DIR / "static"),
)
app.secret_key = auth.secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

# Reachable without logging in: the login page itself and the files a phone needs to install the app.
PUBLIC_PATHS = {"/login", "/healthz", "/offline", "/manifest.webmanifest", "/sw.js"}
UNSAFE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
CSRF_HEADER = ("X-Requested-With", "GreatMega")


# ---- security gate: runs before every request ----------------------------------------
@app.before_request
def guard():
    path = request.path
    if path.startswith("/static/") or path in PUBLIC_PATHS:
        return None

    if auth.configured():
        if not auth.is_logged_in(session):
            if path.startswith("/api/"):
                return jsonify(error="Please log in."), 401
            return redirect(url_for("login"))
    elif not auth.local_request(request):
        return Response(
            "This site is not password protected, so it only answers this computer.\n"
            "On the computer that runs it, run:  py set_password.py\n",
            status=403, mimetype="text/plain")

    # A web page on another site must not be able to press our buttons: every change
    # has to carry a header that browsers only allow our own pages to send.
    if request.method in UNSAFE_METHODS and request.headers.get(CSRF_HEADER[0]) != CSRF_HEADER[1]:
        return jsonify(error="Blocked: missing security header."), 403
    return None


# ---- error handling: registry exceptions become clean JSON errors ----------------------
@app.errorhandler(registry.BotNotFound)
def _not_found(err):
    return jsonify(error=str(err)), 404


@app.errorhandler(registry.ValidationError)
def _invalid(err):
    return jsonify(error=str(err)), 400


@app.errorhandler(registry.BotBusy)
def _busy(err):
    return jsonify(error=str(err)), 409


def _payload() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ---- pages ----------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth.configured():
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("login.html", error=None)

    ip = request.remote_addr or "unknown"
    wait = auth.locked_for(ip)
    if wait:
        return render_template("login.html", error=f"Too many wrong attempts. Try again in {wait} seconds."), 429
    if auth.check_password(request.form.get("password", "")):
        auth.record_success(ip)
        auth.log_in(session)
        return redirect(url_for("index"))
    auth.record_failure(ip)
    return render_template("login.html", error="Wrong password."), 401


@app.post("/logout")
def logout():
    auth.log_out(session)
    return jsonify(ok=True)


@app.get("/healthz")
def healthz():
    return "great-mega", 200, {"Content-Type": "text/plain"}


# ---- installable-app files --------------------------------------------------------------
@app.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest",
                               mimetype="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    resp = send_from_directory(app.static_folder, "sw.js", mimetype="text/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/offline")
def offline():
    return render_template("offline.html")


# ---- password management (from Settings) ---------------------------------------------------
def _check_current_password(data: dict):
    """Returns an error response, or None when the current password is right."""
    ip = request.remote_addr or "unknown"
    wait = auth.locked_for(ip)
    if wait:
        return jsonify(error=f"Too many wrong attempts. Try again in {wait} seconds."), 429
    if not auth.check_password(str(data.get("current_password") or "")):
        auth.record_failure(ip)
        return jsonify(error="Current password is wrong."), 403      # 403, not 401: 401 means "log in again"
    auth.record_success(ip)
    return None


@app.post("/api/auth/password")
def change_password():
    data = _payload()
    if auth.configured():
        error = _check_current_password(data)
        if error:
            return error
    new, repeat = str(data.get("new_password") or ""), str(data.get("repeat_password") or "")
    if new != repeat:
        return jsonify(error="The two new passwords do not match."), 400
    try:
        auth.set_password(new)
    except ValueError as err:
        return jsonify(error=str(err)), 400
    auth.log_in(session)               # you stay signed in; every other device is signed out
    return jsonify(ok=True)


@app.post("/api/auth/remove")
def remove_password():
    if auth.configured():
        error = _check_current_password(_payload())
        if error:
            return error
        auth.clear_password()
    session.clear()
    return jsonify(ok=True)


# ---- API -------------------------------------------------------------------------------
@app.get("/api/state")
def state():
    link = mt5_link.get_link()
    link.ensure_started()                 # connects to MetaTrader 5 in the background (read-only)
    return jsonify(
        mt5=link.snapshot(),
        bots=[b.to_dict() for b in registry.all_bots()],
        activity=registry.activity()[:15],
        instruments=registry.INSTRUMENTS,
        limits={"min_lot": registry.MIN_LOT, "max_lot": registry.MAX_LOT},
        auth={"enabled": auth.configured()},
    )


# ---- MetaTrader 5 (read-only) -------------------------------------------------------------
@app.get("/api/mt5/history")
def mt5_history():
    link = mt5_link.get_link()
    link.ensure_started()
    return jsonify(link.history(request.args.get("days", 30, type=int) or 30))


@app.post("/api/mt5/reconnect")
def mt5_reconnect():
    link = mt5_link.get_link()
    link.ensure_started()
    return jsonify(link.reconnect())


@app.post("/api/mt5/watchlist")
def mt5_watchlist():
    link = mt5_link.get_link()
    try:
        names = link.set_watchlist(_payload().get("symbols"))
    except ValueError as err:
        return jsonify(error=str(err)), 400
    return jsonify(watchlist=names)


@app.get("/api/bots")
def list_bots():
    return jsonify([b.to_dict() for b in registry.all_bots()])


@app.post("/api/bots")
def create_bot():
    return jsonify(registry.create_bot(_payload()).to_dict()), 201


@app.put("/api/bots/<bot_id>")
def update_bot(bot_id):
    return jsonify(registry.update_bot(bot_id, _payload()).to_dict())


@app.delete("/api/bots/<bot_id>")
def delete_bot(bot_id):
    registry.delete_bot(bot_id)
    return jsonify(ok=True)


@app.post("/api/bots/<bot_id>/start")
def start_bot(bot_id):
    return jsonify(registry.start_bot(bot_id).to_dict())


@app.post("/api/bots/<bot_id>/stop")
def stop_bot(bot_id):
    return jsonify(registry.stop_bot(bot_id).to_dict())


@app.post("/api/bots/<bot_id>/lot")
def set_lot(bot_id):
    return jsonify(registry.set_lot(bot_id, _payload().get("lot")).to_dict())


@app.post("/api/bots/start-all")
def start_all():
    return jsonify(changed=registry.start_all())


@app.post("/api/bots/stop-all")
def stop_all():
    return jsonify(changed=registry.stop_all())


# ---- run ---------------------------------------------------------------------------------
def lan_ip() -> str:
    """This computer's address on your Wi-Fi/router (no data is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GREAT MEGA server")
    parser.add_argument("--lan", action="store_true",
                        help="let phones and other devices on your Wi-Fi connect (set a password first)")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    if args.lan:
        if not auth.configured():
            print("\nNo password is set, so other devices would be refused (403).")
            print("Run  py set_password.py  first, then start again with --lan.\n")
        print(f"\nOn your phone (same Wi-Fi) open:  http://{lan_ip()}:{args.port}\n")
        app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
    else:
        app.run(debug=True, port=args.port)
