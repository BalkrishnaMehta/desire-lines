from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any


def route_candidates(candidates: list[dict[str, Any]], max_items: int = 8) -> list[dict[str, Any]]:
    if not candidates:
        return []
    remaining = sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)
    route = [remaining.pop(0)]
    while remaining and len(route) < max_items:
        current = _candidate_end(route[-1])
        next_item = min(remaining, key=lambda item: _distance(current, _candidate_start(item)))
        route.append(next_item)
        remaining.remove(next_item)
    return route


def export_gpx(route: list[dict[str, Any]], target: Path) -> None:
    points = []
    for item in route:
        for lon, lat in item["geometry"]:
            points.append(
                f'      <trkpt lat="{lat:.7f}" lon="{lon:.7f}">'
                f"<name>Desire line {html.escape(item['id'])}</name></trkpt>"
            )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="Desire Lines" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        "  <trk><name>Desire Lines field walk</name><trkseg>\n"
        + "\n".join(points)
        + "\n  </trkseg></trk>\n</gpx>\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build_walk(input_geojson: Path, output_dir: Path, max_items: int = 8) -> dict[str, Any]:
    payload = json.loads(input_geojson.read_text(encoding="utf-8"))
    candidates = []
    for feature in payload["features"]:
        props = feature["properties"]
        review = props.get("review", {})
        if review.get("verdict") not in {"yes", "unclear"}:
            continue
        candidates.append(
            {
                **props,
                "geometry": feature["geometry"]["coordinates"],
            }
        )
    route = route_candidates(candidates, max_items=max_items)
    output_dir.mkdir(parents=True, exist_ok=True)
    export_gpx(route, output_dir / "desire-lines-walk.gpx")
    (output_dir / "field-card.html").write_text(_field_card(route), encoding="utf-8")
    tasks = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": item["geometry"]},
                "properties": {
                    "id": item["id"],
                    "instruction": "Survey only. Do not map from imagery alone.",
                    "id_editor": _id_link(item),
                },
            }
            for item in route
        ],
    }
    (output_dir / "maproulette-tasks.geojson").write_text(
        json.dumps(tasks, indent=2), encoding="utf-8"
    )
    return {"stops": len(route), "gpx": "desire-lines-walk.gpx", "field_card": "field-card.html"}


def _field_card(route: list[dict[str, Any]]) -> str:
    rows = []
    for number, item in enumerate(route, 1):
        review = item.get("review", {})
        rows.append(
            "<li><strong>"
            + html.escape(f"{number}. {review.get('title', item['id'])}")
            + "</strong><br>"
            + html.escape(review.get("diff", "Field check"))
            + '<div class="checks">□ worn &nbsp; □ faint &nbsp; □ gone &nbsp; □ paved</div></li>'
        )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Desire Lines field card</title>
<style>
@page {{ size: A6; margin: 8mm; }} body {{ font: 10pt system-ui; color:#172019; }}
h1 {{ font-size:18pt; margin:0 }} ol {{ padding-left:1.4em }} li {{ margin:9px 0 }}
.checks {{ margin-top:4px }} .rule {{ border-top:2px solid; margin:6px 0 }}
</style><body><h1>Desire Lines</h1><div>Pull requests the city never merged.</div>
<div class="rule"></div><p>Walk. Look. Tick what is really there. Never edit OSM from
aerial imagery alone.</p><ol>{''.join(rows)}</ol>
<p>Map only what you personally verify.</p></body></html>"""


def _id_link(item: dict[str, Any]) -> str:
    lon, lat = _candidate_start(item)
    return f"https://www.openstreetmap.org/edit?editor=id#map=20/{lat:.7f}/{lon:.7f}"


def _candidate_start(item: dict[str, Any]) -> tuple[float, float]:
    lon, lat = item["geometry"][0]
    return float(lon), float(lat)


def _candidate_end(item: dict[str, Any]) -> tuple[float, float]:
    lon, lat = item["geometry"][-1]
    return float(lon), float(lat)


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    lon_scale = math.cos(math.radians((first[1] + second[1]) / 2))
    return math.hypot((first[0] - second[0]) * lon_scale, first[1] - second[1])

