from datetime import timedelta

from app.timeutil import today_ist


def test_live_map_scoped_by_depot(client, login):
    all_v = client.get("/api/avls/live", headers=login("control1")).json()["vehicles"]
    assert len(all_v) == 50
    mgr = client.get("/api/avls/live", headers=login("manager_nsd")).json()["vehicles"]
    assert 0 < len(mgr) < len(all_v)
    assert {v["depot_code"] for v in mgr} == {"NSD"}


def test_manager_cannot_request_other_depot(client, login):
    depots = client.get("/api/depots", headers=login("admin1")).json()
    other = next(d["id"] for d in depots if d["code"] == "AVD")
    r = client.get(f"/api/avls/live?depot_id={other}", headers=login("manager_nsd"))
    assert r.status_code == 403


def test_geofence_breach_alert_present(client, login):
    alerts = client.get("/api/avls/live", headers=login("control1")).json()["alerts"]
    assert any(a["type"] == "geofence_breach" for a in alerts)


def test_trail_and_history(client, login):
    h = login("control1")
    vehicles = client.get("/api/avls/live", headers=h).json()["vehicles"]
    on_duty = next(v for v in vehicles if v["driver"])
    trail = client.get(f"/api/avls/vehicles/{on_duty['vehicle_id']}/trail?minutes=30", headers=h).json()
    assert len(trail["pings"]) > 10
    yday = (today_ist() - timedelta(days=1)).isoformat()
    for v in vehicles:
        hist = client.get(f"/api/avls/vehicles/{v['vehicle_id']}/history?day={yday}", headers=h).json()
        if hist["pings"]:
            assert hist["summary"]["distance_km"] > 1
            return
    raise AssertionError("no vehicle had history for yesterday")


def test_tick_adds_pings():
    from app import tick
    import random
    from app.database import SessionLocal
    with SessionLocal() as db:
        buses = tick.load_buses(db, random.Random(1), {})
        assert len(buses) == 40
        assert tick.tick_once(db, buses, random.Random(1)) == 40
