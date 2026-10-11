"""Copy layer GeoJSON into layers-city, keeping features that touch the city bbox.

A feature is kept when any coordinate, or a polygon/multipolygon centroid, falls
inside west/south/east/north. Source files under layers/ are never modified.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "generated" / "layers"
TARGET = ROOT / "data" / "generated" / "layers-city"
LAYERS = ("paths.geojson", "green.geojson", "barriers.geojson", "attractors.geojson")

WEST = 5.075
SOUTH = 52.055
EAST = 5.155
NORTH = 52.115


def _inside(lon: float, lat: float) -> bool:
    return WEST <= lon <= EAST and SOUTH <= lat <= NORTH


def _walk_coords(coords, hits: list[tuple[float, float]]) -> None:
    if not coords:
        return
    first = coords[0]
    if isinstance(first, (int, float)):
        hits.append((float(coords[0]), float(coords[1])))
        return
    for item in coords:
        _walk_coords(item, hits)


def _ring_centroid(ring: list) -> tuple[float, float] | None:
    if len(ring) < 3:
        return None
    area = 0.0
    cx = 0.0
    cy = 0.0
    points = ring[:-1] if ring[0] == ring[-1] and len(ring) > 1 else ring
    if len(points) < 3:
        return None
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if area == 0:
        lon = sum(point[0] for point in points) / len(points)
        lat = sum(point[1] for point in points) / len(points)
        return lon, lat
    area *= 0.5
    return cx / (6 * area), cy / (6 * area)


def _centroids(geometry: dict) -> list[tuple[float, float]]:
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Polygon" and coords:
        centroid = _ring_centroid(coords[0])
        return [centroid] if centroid else []
    if kind == "MultiPolygon" and coords:
        found = []
        for polygon in coords:
            if polygon:
                centroid = _ring_centroid(polygon[0])
                if centroid:
                    found.append(centroid)
        return found
    return []


def keep_feature(feature: dict) -> bool:
    geometry = feature.get("geometry") or {}
    coords: list[tuple[float, float]] = []
    _walk_coords(geometry.get("coordinates"), coords)
    if any(_inside(lon, lat) for lon, lat in coords):
        return True
    return any(_inside(lon, lat) for lon, lat in _centroids(geometry))


def filter_layer(name: str) -> dict[str, int]:
    source = SOURCE / name
    target = TARGET / name
    print(f"reading {name} ({source.stat().st_size / 1_048_576:.1f} MB)", flush=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    kept = [feature for feature in features if keep_feature(feature)]
    out = {"type": "FeatureCollection", "features": kept}
    target.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {name}: {len(kept)}/{len(features)}", flush=True)
    return {"source": len(features), "kept": len(kept)}


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    summary = {name: filter_layer(name) for name in LAYERS}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
