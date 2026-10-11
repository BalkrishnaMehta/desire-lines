from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, Point, Polygon

from .geo import feature, write_geojson

WALKABLE = {
    "footway",
    "path",
    "pedestrian",
    "living_street",
    "residential",
    "service",
    "steps",
    "track",
    "unclassified",
    "tertiary",
    "secondary",
}
GREEN_LANDUSE = {"grass", "recreation_ground", "meadow", "village_green", "forest"}
GREEN_LEISURE = {"park", "common", "nature_reserve", "garden", "playground"}
BARRIERS = {"fence", "wall", "hedge", "retaining_wall"}
ATTRACTOR_AMENITIES = {"school", "university", "marketplace", "community_centre"}


def classify_tags(tags: dict[str, str]) -> set[str]:
    kinds: set[str] = set()
    if tags.get("highway") in WALKABLE and tags.get("foot") != "no":
        kinds.add("path")
        if tags.get("informal") == "yes":
            kinds.add("informal")
    if tags.get("landuse") in GREEN_LANDUSE or tags.get("leisure") in GREEN_LEISURE:
        kinds.add("green")
    if tags.get("natural") in {"wood", "grassland", "scrub"}:
        kinds.add("green")
    if tags.get("building") or tags.get("natural") == "water":
        kinds.add("barrier")
    if tags.get("barrier") in BARRIERS:
        kinds.add("barrier")
    if (
        tags.get("public_transport") in {"platform", "stop_position"}
        or tags.get("highway") == "bus_stop"
        or tags.get("railway") in {"tram_stop", "station"}
        or tags.get("entrance")
        or tags.get("amenity") in ATTRACTOR_AMENITIES
        or tags.get("shop")
    ):
        kinds.add("attractor")
    return kinds


def extract_pbf(
    source: Path,
    output_dir: Path,
    bbox: tuple[float, float, float, float] = (5.02, 52.02, 5.22, 52.18),
) -> dict[str, int]:
    """Extract a compact set of map layers from an OSM PBF.

    The handler intentionally reads ways and nodes only. That covers mapped paths,
    closed green-space/building ways, and point attractors without holding the full
    regional extract in memory.
    """
    try:
        import osmium
    except ImportError as exc:  # pragma: no cover - dependency check
        raise RuntimeError("Install the 'osmium' package to read .osm.pbf files") from exc

    west, south, east, north = bbox
    layers: dict[str, list[dict[str, Any]]] = defaultdict(list)

    class Handler(osmium.SimpleHandler):
        def node(self, node):
            if not node.location.valid():
                return
            lon, lat = node.location.lon, node.location.lat
            if not (west <= lon <= east and south <= lat <= north):
                return
            tags = dict(node.tags)
            if "attractor" in classify_tags(tags):
                layers["attractors"].append(
                    feature(
                        Point(lon, lat),
                        {
                            "osm_id": f"node/{node.id}",
                            "kind": _attractor_kind(tags),
                            "name": tags.get("name", ""),
                        },
                    )
                )

        def way(self, way):
            try:
                coords = [(n.lon, n.lat) for n in way.nodes]
            except osmium.InvalidLocationError:
                return
            if len(coords) < 2 or not any(
                west <= lon <= east and south <= lat <= north for lon, lat in coords
            ):
                return
            tags = dict(way.tags)
            kinds = classify_tags(tags)
            common = {
                "osm_id": f"way/{way.id}",
                "name": tags.get("name", ""),
                "highway": tags.get("highway", ""),
                "surface": tags.get("surface", ""),
            }
            if "path" in kinds:
                props = {**common, "informal": "informal" in kinds}
                layers["paths"].append(feature(LineString(coords), props))
            if coords[0] == coords[-1] and len(coords) >= 4:
                polygon = Polygon(coords)
                if polygon.is_valid and "green" in kinds:
                    layers["green"].append(feature(polygon, common))
                if polygon.is_valid and "barrier" in kinds:
                    layers["barriers"].append(feature(polygon, common))
            elif "barrier" in kinds:
                layers["barriers"].append(feature(LineString(coords), common))

    handler = Handler()
    handler.apply_file(str(source), locations=True, idx="flex_mem")
    for name in ("paths", "green", "barriers", "attractors"):
        write_geojson(layers[name], output_dir / f"{name}.geojson")
    return {name: len(layers[name]) for name in ("paths", "green", "barriers", "attractors")}


def _attractor_kind(tags: dict[str, str]) -> str:
    for key in ("public_transport", "highway", "railway", "entrance", "amenity", "shop"):
        if tags.get(key):
            return tags[key]
    return "destination"

