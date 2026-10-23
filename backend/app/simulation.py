"""Shared helpers for the seed script and the tick script (the fake-GPS generator)."""
import random

from .geo import densify, haversine_m

SPACING_M = 50


def route_loop(coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Out-and-back dense polyline for a route, so a simulated bus can circulate forever."""
    path = densify(coords, SPACING_M)
    return path + path[-2:0:-1]


def nearest_index(loop: list[tuple[float, float]], lat: float, lng: float) -> int:
    best, best_d = 0, float("inf")
    for i, (a, b) in enumerate(loop):
        d = (a - lat) ** 2 + (b - lng) ** 2
        if d < best_d:
            best, best_d = i, d
    return best


def vehicle_speed_kmh(vehicle_id: int, rng: random.Random) -> float:
    """Every 4th bus is 'stuck in traffic' (slow); the rest cruise at city speeds."""
    if vehicle_id % 4 == 0:
        return max(4.0, rng.uniform(7, 14))
    return rng.uniform(20, 36)


def planned_offsets(coords: list[tuple[float, float]], avg_kmh: float = 17.0, dwell_min: float = 1.5) -> list[int]:
    """Planned minutes-from-start for each stop, from distance at an average city speed plus dwell."""
    offsets, acc = [0], 0.0
    for a, b in zip(coords, coords[1:]):
        acc += haversine_m(*a, *b) / 1000 / avg_kmh * 60 + dwell_min
        offsets.append(max(offsets[-1] + 2, round(acc)))
    return offsets
