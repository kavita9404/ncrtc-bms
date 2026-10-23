"""Small geo helpers (no PostGIS needed at this scale)."""
import math

EARTH_M = 6_371_000


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(a))


def point_in_polygon(lat: float, lng: float, geojson: dict | None) -> bool:
    """Ray casting on the outer ring of a GeoJSON Polygon. Missing polygon -> treated as inside."""
    if not geojson:
        return True
    ring = geojson["coordinates"][0]
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]  # lng, lat
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def square_polygon(lat: float, lng: float, half_m: float = 250) -> dict:
    dlat = half_m / 111_320
    dlng = half_m / (111_320 * math.cos(math.radians(lat)))
    ring = [
        [lng - dlng, lat - dlat], [lng + dlng, lat - dlat],
        [lng + dlng, lat + dlat], [lng - dlng, lat + dlat], [lng - dlng, lat - dlat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def densify(points: list[tuple[float, float]], spacing_m: float = 50) -> list[tuple[float, float]]:
    """Insert points along a polyline so consecutive points are ~spacing_m apart."""
    out: list[tuple[float, float]] = []
    for (a_lat, a_lng), (b_lat, b_lng) in zip(points, points[1:]):
        d = haversine_m(a_lat, a_lng, b_lat, b_lng)
        n = max(1, int(d // spacing_m))
        for k in range(n):
            f = k / n
            out.append((a_lat + (b_lat - a_lat) * f, a_lng + (b_lng - a_lng) * f))
    if points:
        out.append(points[-1])
    return out


def path_length_m(points: list[tuple[float, float]]) -> float:
    return sum(haversine_m(*a, *b) for a, b in zip(points, points[1:]))
