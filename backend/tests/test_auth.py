def test_login_ok_and_me(client, login):
    h = login("admin1")
    assert client.get("/api/auth/me", headers=h).json()["role"] == "admin"


def test_wrong_password_rejected(client):
    r = client.post("/api/auth/login", data={"username": "admin1", "password": "nope"})
    assert r.status_code == 401


def test_every_route_needs_login(client):
    for path in ("/api/avls/live", "/api/incidents", "/api/notices", "/api/routes", "/api/depots"):
        assert client.get(path).status_code == 401, path


def test_passwords_are_hashed():
    from app.database import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        assert all(u.password_hash.startswith("$2") for u in db.query(User).all())


def test_driver_cannot_open_ops_pages(client, login):
    h = login("driver1")
    assert client.get("/api/avls/live", headers=h).status_code == 403
    assert client.post("/api/routes", headers=h, json={}).status_code == 403
