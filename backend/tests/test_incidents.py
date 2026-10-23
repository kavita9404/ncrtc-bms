def test_panic_creates_p1_with_vehicle(client, login):
    h = login("driver2")
    r = client.post("/api/incidents/panic", headers=h, json={})
    assert r.status_code == 201
    i = r.json()
    assert i["severity"] == "P1" and i["status"] == "open" and i["vehicle_id"] and i["lat"]
    # control room sees it in the queue
    queue = client.get("/api/incidents?severity=P1&status=open", headers=login("control1")).json()
    assert any(x["id"] == i["id"] for x in queue)


def test_workflow_requires_notes_and_order(client, login):
    mgr = login("manager_nsd")
    vehicles = client.get("/api/vehicles", headers=mgr).json()
    i = client.post("/api/incidents", headers=mgr,
                    json={"type": "breakdown", "severity": "P2", "description": "Flat tyre near Sec-18",
                          "vehicle_id": vehicles[0]["id"]}).json()
    url = f"/api/incidents/{i['id']}/transition"
    # cannot skip steps
    assert client.post(url, headers=mgr, json={"to_status": "resolved", "note": "done"}).status_code == 409
    # note is mandatory
    assert client.post(url, headers=mgr, json={"to_status": "acknowledged", "note": ""}).status_code == 422
    for s in ("acknowledged", "in_progress", "resolved", "closed"):
        r = client.post(url, headers=mgr, json={"to_status": s, "note": f"moving to {s}"})
        assert r.status_code == 200, r.text
    detail = client.get(f"/api/incidents/{i['id']}", headers=mgr).json()
    assert detail["status"] == "closed" and len(detail["events"]) == 5 and detail["resolved_at"]


def test_driver_only_sees_own_incidents_and_cannot_transition(client, login):
    drv = login("driver10")  # has no seeded incidents
    me = client.get("/api/auth/me", headers=drv).json()
    mine = client.post("/api/incidents/panic", headers=drv, json={}).json()
    listed = client.get("/api/incidents", headers=drv).json()
    assert [i["id"] for i in listed] == [mine["id"]]
    assert all(i["raised_by"] == me["id"] for i in listed)
    r = client.post(f"/api/incidents/{mine['id']}/transition", headers=drv, json={"to_status": "acknowledged", "note": "x y z"})
    assert r.status_code == 403


def test_depot_scoping_for_incidents(client, login):
    nsd = {i["depot_code"] for i in client.get("/api/incidents", headers=login("manager_nsd")).json()}
    assert nsd == {"NSD"}
    mgr_other = login("manager_avd")
    nsd_incident = client.get("/api/incidents", headers=login("manager_nsd")).json()[0]
    assert client.get(f"/api/incidents/{nsd_incident['id']}", headers=mgr_other).status_code == 403


def test_assign_and_sla(client, login):
    ctrl = login("control1")
    inc = next(i for i in client.get("/api/incidents?severity=P1", headers=ctrl).json() if i["status"] == "open")
    me = client.get("/api/auth/me", headers=ctrl).json()
    r = client.post(f"/api/incidents/{inc['id']}/assign", headers=ctrl, json={"assignee_id": me["id"]})
    assert r.status_code == 200 and r.json()["assigned_to"] == me["id"]
    seeded_breach = [i for i in client.get("/api/incidents", headers=ctrl).json() if i["sla_breached"]]
    assert seeded_breach  # the 95-minute-old P1 is past its 1-hour SLA
