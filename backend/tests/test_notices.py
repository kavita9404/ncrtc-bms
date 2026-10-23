def test_audience_and_read_receipts(client, login):
    admin = login("admin1")
    depots = client.get("/api/depots", headers=admin).json()
    gzb = next(d for d in depots if d["code"] == "GZB")["id"]
    n = client.post("/api/notices", headers=admin, json={
        "title": "GZB gate closure", "body": "Gate 2 closed tomorrow.",
        "audience": {"type": "depot", "depot_id": gzb}, "requires_ack": True}).json()

    gzb_driver = next(u for u in client.get("/api/users?role=driver", headers=admin).json() if u["depot_id"] == gzb)
    h_in = login(gzb_driver["username"])
    h_out = login("driver1")  # NSD driver
    assert any(x["id"] == n["id"] for x in client.get("/api/notices", headers=h_in).json())
    assert not any(x["id"] == n["id"] for x in client.get("/api/notices", headers=h_out).json())
    assert client.post(f"/api/notices/{n['id']}/read", headers=h_out).status_code == 404

    assert client.post(f"/api/notices/{n['id']}/read", headers=h_in).json()["read_at"]
    assert client.post(f"/api/notices/{n['id']}/ack", headers=h_in).json()["ack_at"]

    rec = client.get(f"/api/notices/{n['id']}/receipts", headers=admin).json()
    assert rec["read"] == 1 and rec["acknowledged"] == 1 and rec["total"] > 5
    assert client.get(f"/api/notices/{n['id']}/receipts", headers=h_in).status_code == 403


def test_only_admin_publishes(client, login):
    r = client.post("/api/notices", headers=login("manager_nsd"),
                    json={"title": "Hi there", "body": "x", "audience": {"type": "all"}})
    assert r.status_code == 403


def test_executive_report(client, login):
    rep = client.get("/api/reports/daily", headers=login("exec1")).json()
    assert len(rep["depots"]) == 4 and rep["total"]["duties"] > 30
    assert client.get("/api/reports/daily", headers=login("manager_nsd")).status_code == 403
