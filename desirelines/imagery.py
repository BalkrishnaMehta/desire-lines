from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw
from shapely.geometry import shape

from .geo import write_geojson

PDOK_TILE = (
    "https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0"
    "?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=Actueel_ortho25"
    "&STYLE=&FORMAT=image/jpeg&tileMatrixSet=EPSG:3857"
    "&tileMatrix={z}&tileRow={y}&tileCol={x}"
)


def excess_green(image: np.ndarray) -> np.ndarray:
    pixels = image.astype(np.float32)
    return 2 * pixels[..., 1] - pixels[..., 0] - pixels[..., 2]


def wear_score(
    exg: np.ndarray, corridor: np.ndarray, controls: np.ndarray
) -> dict[str, float]:
    if not corridor.any() or not controls.any():
        return {"wear": 0.0, "continuity": 0.0}
    corridor_values = exg[corridor]
    control_values = exg[controls]
    spread = max(float(np.std(control_values)), 1.0)
    wear = (float(np.mean(control_values)) - float(np.mean(corridor_values))) / spread
    threshold = float(np.mean(control_values) - 0.5 * spread)
    continuity = float(np.mean(corridor_values < threshold))
    return {"wear": wear, "continuity": continuity}


def score_imagery(
    input_geojson: Path,
    output_geojson: Path,
    cache_dir: Path,
    chip_dir: Path,
    *,
    zoom: int = 19,
    limit: int = 80,
) -> dict[str, float]:
    import json

    payload = json.loads(input_geojson.read_text(encoding="utf-8"))
    features = sorted(
        payload["features"],
        key=lambda item: item["properties"]["detour_ratio"],
        reverse=True,
    )[:limit]
    cache_dir.mkdir(parents=True, exist_ok=True)
    chip_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "DesireLines/0.1 (open research; hackathon)"
    scores = []
    for item in features:
        try:
            chip, line_points = _candidate_chip(
                shape(item["geometry"]), cache_dir, session, zoom=zoom
            )
            corridor, controls = _line_masks(chip.size, line_points)
            values = wear_score(excess_green(np.asarray(chip)), corridor, controls)
            item["properties"].update({key: round(value, 3) for key, value in values.items()})
            chip_name = f'{item["properties"]["id"]}.jpg'
            item["properties"]["chip"] = f"chips/{chip_name}"
            overlay = chip.copy()
            draw = ImageDraw.Draw(overlay)
            draw.line(line_points, fill=(255, 70, 50), width=3)
            overlay.save(chip_dir / chip_name, quality=90)
            scores.append(values["wear"])
        except (requests.RequestException, OSError, ValueError) as exc:
            item["properties"].update(
                {"wear": 0.0, "continuity": 0.0, "imagery_error": str(exc)[:160]}
            )
    write_geojson(features, output_geojson)
    return {
        "scored": len(features),
        "mean_wear": round(float(np.mean(scores)), 3) if scores else 0.0,
    }


def _candidate_chip(line, cache_dir: Path, session: requests.Session, *, zoom: int):
    global_points = [_lonlat_to_global_pixel(lon, lat, zoom) for lon, lat in line.coords]
    pad = 80
    min_x = math.floor(min(point[0] for point in global_points) - pad)
    max_x = math.ceil(max(point[0] for point in global_points) + pad)
    min_y = math.floor(min(point[1] for point in global_points) - pad)
    max_y = math.ceil(max(point[1] for point in global_points) + pad)
    first_tx, last_tx = min_x // 256, max_x // 256
    first_ty, last_ty = min_y // 256, max_y // 256
    canvas = Image.new("RGB", ((last_tx - first_tx + 1) * 256, (last_ty - first_ty + 1) * 256))
    for tx in range(first_tx, last_tx + 1):
        for ty in range(first_ty, last_ty + 1):
            tile = _get_tile(tx, ty, zoom, cache_dir, session)
            canvas.paste(tile, ((tx - first_tx) * 256, (ty - first_ty) * 256))
    left, top = min_x - first_tx * 256, min_y - first_ty * 256
    chip = canvas.crop((left, top, left + max_x - min_x, top + max_y - min_y))
    local_points = [(x - min_x, y - min_y) for x, y in global_points]
    return chip, local_points


def _get_tile(
    x: int, y: int, z: int, cache_dir: Path, session: requests.Session
) -> Image.Image:
    path = cache_dir / str(z) / str(x) / f"{y}.jpg"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = session.get(PDOK_TILE.format(x=x, y=y, z=z), timeout=30)
        response.raise_for_status()
        path.write_bytes(response.content)
        time.sleep(0.04)
    return Image.open(path).convert("RGB")


def _line_masks(
    size: tuple[int, int], points: list[tuple[float, float]]
) -> tuple[np.ndarray, np.ndarray]:
    corridor_img = Image.new("1", size)
    control_img = Image.new("1", size)
    ImageDraw.Draw(corridor_img).line(points, fill=1, width=5)
    if len(points) < 2:
        return np.asarray(corridor_img, dtype=bool), np.asarray(control_img, dtype=bool)
    x1, y1 = points[0]
    x2, y2 = points[-1]
    length = max(math.hypot(x2 - x1, y2 - y1), 1)
    nx, ny = -(y2 - y1) / length, (x2 - x1) / length
    draw = ImageDraw.Draw(control_img)
    for offset in (-14, 14):
        shifted = [(x + nx * offset, y + ny * offset) for x, y in points]
        draw.line(shifted, fill=1, width=7)
    return np.asarray(corridor_img, dtype=bool), np.asarray(control_img, dtype=bool)


def _lonlat_to_global_pixel(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    scale = 256 * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    sin_lat = math.sin(math.radians(max(min(lat, 85.05112878), -85.05112878)))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y

