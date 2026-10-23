from datetime import timedelta

from app.timeutil import today_ist


def _roster(client, h, depot_id, day):
    ws = day - timedelta(days=day.weekday())
    return client.get(f"/api/roster?depot_id={depot_id}&week_start={ws}", headers=h).json()


def test_assign_conflicts_and_publish(client, login):
    h = login("manager_gzb")
    me = client.get("/api/auth/me", headers=h).json()
    day = today_ist() + timedelta(days=20)  # nothing seeded there
    r = _roster(client, h, me["depot_id"], day)
    drv, veh, route = r["drivers"][0]["id"], r["vehicles"][0]["id"], r["routes"][0]["id"]
    body = {"date": day.isoformat(), "driver_id": drv, "vehicle_id": veh, "route_id": route}

    created = client.post("/api/duties", headers=h, json=body)
    assert created.status_code == 201 and created.json()["status"] == "draft"

    # same driver, different bus, same day -> blocked
    again = client.post("/api/duties", headers=h, json={**body, "vehicle_id": r["vehicles"][1]["id"]})
    assert again.status_code == 409 and "Driver" in again.json()["detail"]
    # same bus, different driver -> blocked
    again = client.post("/api/duties", headers=h, json={**body, "driver_id": r["drivers"][1]["id"]})
    assert again.status_code == 409 and "Vehicle" in again.json()["detail"]

    pub = client.post("/api/duties/publish", headers=h,
                      json={"depot_id": me["depot_id"], "date_from": day.isoformat(), "date_to": day.isoformat()})
    assert pub.json()["published"] == 1


def test_manager_cannot_schedule_other_depot(client, login):
    h = login("manager_nsd")
    other = login("manager_avd")
    me = client.get("/api/auth/me", headers=other).json()
    day = today_ist() + timedelta(days=25)
    r = _roster(client, other, me["depot_id"], day)
    body = {"date": day.isoformat(), "driver_id": r["drivers"][0]["id"], "vehicle_id": r["vehicles"][0]["id"],
            "route_id": r["routes"][0]["id"]}
    assert client.post("/api/duties", headers=h, json=body).status_code == 403
    assert client.get(f"/api/roster?depot_id={me['depot_id']}&week_start={day}", headers=h).status_code == 403


def test_driver_sees_and_acknowledges_duty(client, login):
    h = login("driver1")
    duties = client.get("/api/me/duties", headers=h).json()
    today = next(d for d in duties if d["date"] == today_ist().isoformat())
    assert today["status"] == "published" and len(today["stops"]) >= 6
    acked = client.post(f"/api/duties/{today['id']}/ack", headers=h).json()
    assert acked["status"] == "acknowledged" and acked["ack_at"]
    # someone else's duty
    other = client.get("/api/duties/search", headers=login("admin1")).json()
    foreign = next(d for d in other if d["driver_id"] != today["driver_id"])
    assert client.post(f"/api/duties/{foreign['id']}/ack", headers=h).status_code == 403


def test_route_crud_admin_only(client, login):
    admin = login("admin1")
    depot = client.get("/api/depots", headers=admin).json()[0]["id"]
    stops = client.get("/api/stops", headers=admin).json()[:3]
    body = {"code": "TST-1", "name": "Test route", "depot_id": depot,
            "stops": [{"stop_id": s["id"], "planned_offset_min": i * 10} for i, s in enumerate(stops)]}
    assert client.post("/api/routes", headers=login("manager_nsd"), json=body).status_code == 403
    r = client.post("/api/routes", headers=admin, json=body)
    assert r.status_code == 201 and r.json()["duration_min"] == 20
    bad = {**body, "code": "TST-2", "stops": body["stops"][::-1]}
    assert client.post("/api/routes", headers=admin, json=bad).status_code == 422  # times go backwards
    assert client.delete(f"/api/routes/{r.json()['id']}", headers=admin).status_code == 204
