from __future__ import annotations

import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import LineString, mapping, shape
from shapely.ops import transform, unary_union

WGS84_TO_METRIC = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
METRIC_TO_WGS84 = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)
NEAREST_INFORMAL_CAP = 9999.0


def clamp_nearest_informal(properties: dict[str, Any], cap: float = NEAREST_INFORMAL_CAP) -> None:
    value = properties.get("nearest_informal_m")
    if value is None:
        return
    try:
        number = float(value)
    except (TypeError, ValueError):
        properties["nearest_informal_m"] = cap
        return
    if not math.isfinite(number) or number > cap:
        properties["nearest_informal_m"] = cap


def to_metric(geometry):
    return transform(WGS84_TO_METRIC.transform, geometry)


def to_wgs84(geometry):
    return transform(METRIC_TO_WGS84.transform, geometry)


def fraction_inside(line: LineString, polygons: Iterable) -> float:
    areas = list(polygons)
    if not areas or line.length == 0:
        return 0.0
    return line.intersection(unary_union(areas)).length / line.length


def write_geojson(features: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for item in features:
        props = item.get("properties")
        if isinstance(props, dict):
            clamp_nearest_informal(props)
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def read_geojson(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def feature(geometry, properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": mapping(geometry), "properties": properties}


def geometry(item: dict[str, Any]):
    return shape(item["geometry"])

