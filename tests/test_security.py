import json, os, sys, tempfile

_TMP = tempfile.TemporaryDirectory()
os.environ["GREAT_MEGA_DATA"] = _TMP.name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import auth
from app import app

H = {"X-Requested-With": "GreatMega"}


def client(remote="127.0.0.1", header=True):
    cl = app.test_client()
    cl.environ_base["REMOTE_ADDR"] = remote
    if header:
        cl.environ_base["HTTP_X_REQUESTED_WITH"] = "GreatMega"
    return cl


def reset():
    auth.clear_password()
    auth._fails.clear()


# ---------------- no password set: only this computer may use the site -----------------
def test_unprotected_site_is_local_only():
    reset()
    assert client().get("/api/state").status_code == 200
    assert client(remote="192.168.1.50").get("/api/state").status_code == 403       # another device
    assert client(remote="192.168.1.50").get("/").status_code == 403
    assert client().get("/api/state", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 403   # via a tunnel
    assert client().get("/api/state", headers={"Tailscale-User-Login": "x@y"}).status_code == 403
    assert client().get("/api/state", base_url="http://evil.example").status_code == 403           # DNS-rebinding style


def test_cross_site_requests_are_blocked():
    reset()
    plain = client(header=False)
    assert plain.post("/api/bots/start-all").status_code == 403                      # no security header
    assert plain.post("/api/bots/stop-all", headers=H).status_code == 200            # with header
    assert plain.get("/api/state").status_code == 200                                # reading is fine


# ---------------- setting a password from the Settings page ------------------------------
def test_set_password_rules():
    reset()
    cl = client()
    post = lambda **kw: cl.post("/api/auth/password", json=kw)
    assert post(new_password="short", repeat_password="short").status_code == 400
    assert post(new_password="longenough1", repeat_password="different1").status_code == 400
    assert not auth.configured()
    assert post(new_password="longenough1", repeat_password="longenough1").status_code == 200
    assert auth.configured()
    assert cl.get("/api/state").get_json()["auth"]["enabled"] is True                # creator stays signed in
    assert "longenough1" not in open(auth.AUTH_FILE).read()                          # only a hash is stored


# ---------------- login, logout and lockout --------------------------------------------------
def test_login_flow():
    reset(); auth.set_password("correct horse 1")
    anon = client()
    r = anon.get("/")
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    assert anon.get("/api/state").status_code == 401
    for public in ("/login", "/manifest.webmanifest", "/sw.js", "/offline", "/healthz", "/static/css/style.css"):
        assert anon.get(public).status_code == 200, public

    assert anon.post("/login", data={"password": "wrong"}).status_code == 401
    r = anon.post("/login", data={"password": "correct horse 1"})
    assert r.status_code == 302
    assert anon.get("/api/state").status_code == 200
    assert anon.get("/").status_code == 200

    anon.post("/logout")
    assert anon.get("/api/state").status_code == 401


def test_remote_device_can_log_in_when_password_set():
    reset(); auth.set_password("correct horse 1")
    phone = client(remote="192.168.1.50")
    assert phone.get("/api/state").status_code == 401
    assert phone.post("/login", data={"password": "correct horse 1"}).status_code == 302
    assert phone.get("/api/state").status_code == 200


def test_lockout_after_repeated_failures():
    reset(); auth.set_password("correct horse 1")
    attacker = client(remote="10.9.9.9")
    for _ in range(auth.MAX_FAILS):
        assert attacker.post("/login", data={"password": "nope"}).status_code == 401
    r = attacker.post("/login", data={"password": "correct horse 1"})                # even the right one
    assert r.status_code == 429
    assert client(remote="10.1.1.1").post("/login", data={"password": "correct horse 1"}).status_code == 302


# ---------------- changing / removing the password ------------------------------------------------
def test_change_password_signs_out_other_devices():
    reset(); auth.set_password("old password 1")
    me, other = client(), client(remote="192.168.1.50")
    me.post("/login", data={"password": "old password 1"})
    other.post("/login", data={"password": "old password 1"})
    assert other.get("/api/state").status_code == 200

    bad = me.post("/api/auth/password", json={"current_password": "WRONG", "new_password": "new password 2", "repeat_password": "new password 2"})
    assert bad.status_code == 403
    ok = me.post("/api/auth/password", json={"current_password": "old password 1", "new_password": "new password 2", "repeat_password": "new password 2"})
    assert ok.status_code == 200
    assert me.get("/api/state").status_code == 200                                    # I stay in
    assert other.get("/api/state").status_code == 401                                 # they are signed out
    assert auth.check_password("new password 2") and not auth.check_password("old password 1")


def test_remove_password_needs_current_password():
    reset(); auth.set_password("some password 1")
    me = client()
    me.post("/login", data={"password": "some password 1"})
    assert me.post("/api/auth/remove", json={"current_password": "nope"}).status_code == 403
    assert auth.configured()
    assert me.post("/api/auth/remove", json={"current_password": "some password 1"}).status_code == 200
    assert not auth.configured()
    assert client().get("/api/state").status_code == 200                              # local works again
    assert client(remote="192.168.1.50").get("/api/state").status_code == 403         # remote does not


def test_password_hash_and_secret_persist():
    reset(); auth.set_password("persist me 123")
    data = json.load(open(auth.AUTH_FILE))
    assert data["password_hash"] and data["secret_key"] and "persist me" not in json.dumps(data)


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn(); print("ok", name)
    finally:
        _TMP.cleanup()
