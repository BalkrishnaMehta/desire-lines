from __future__ import annotations

import json
from pathlib import Path

import click

from .fetch import extract_pbf
from .imagery import score_imagery
from .predict import build_candidates
from .review import review_candidates
from .score import evaluate_models
from .walk import build_walk

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GENERATED = ROOT / "data" / "generated"
LAYERS = GENERATED / "layers"
SITE = ROOT / "site"


@click.group()
def main() -> None:
    """Find pedestrian pull requests the city never merged."""


@main.command()
@click.option("--pbf", type=click.Path(path_type=Path), default=RAW / "utrecht-latest.osm.pbf")
@click.option("--output", type=click.Path(path_type=Path), default=LAYERS)
def fetch(pbf: Path, output: Path) -> None:
    _show(extract_pbf(pbf, output))


@main.command()
@click.option("--layers", type=click.Path(path_type=Path), default=LAYERS)
@click.option("--output", type=click.Path(path_type=Path), default=GENERATED / "candidates.geojson")
def predict(layers: Path, output: Path) -> None:
    _show(build_candidates(layers, output))


@main.command("wear")
@click.option("--input", "source", type=click.Path(path_type=Path), default=GENERATED / "candidates.geojson")
@click.option("--output", type=click.Path(path_type=Path), default=GENERATED / "wear.geojson")
@click.option("--limit", default=80, show_default=True)
def wear_command(source: Path, output: Path, limit: int) -> None:
    _show(
        score_imagery(
            source,
            output,
            ROOT / "data" / "cache" / "pdok",
            SITE / "chips",
            limit=limit,
        )
    )


@main.command()
@click.option("--input", "source", type=click.Path(path_type=Path), default=GENERATED / "wear.geojson")
@click.option("--output", type=click.Path(path_type=Path), default=GENERATED / "scored.geojson")
def score(source: Path, output: Path) -> None:
    _show(evaluate_models(source, output, GENERATED / "metrics.json"))


@main.command()
@click.option("--input", "source", type=click.Path(path_type=Path), default=GENERATED / "scored.geojson")
@click.option("--output", type=click.Path(path_type=Path), default=GENERATED / "reviewed.geojson")
@click.option("--limit", default=20, show_default=True)
def review(source: Path, output: Path, limit: int) -> None:
    _show(review_candidates(source, output, SITE / "chips", limit=limit))


@main.command()
@click.option("--input", "source", type=click.Path(path_type=Path), default=GENERATED / "reviewed.geojson")
@click.option("--output", type=click.Path(path_type=Path), default=SITE / "downloads")
def walk(source: Path, output: Path) -> None:
    _show(build_walk(source, output))


@main.command()
def site() -> None:
    from .site import build_site

    _show(build_site(GENERATED, SITE))


@main.command()
@click.option("--skip-fetch", is_flag=True)
@click.option("--wear-limit", default=80, show_default=True)
@click.option("--review-limit", default=20, show_default=True)
def all(skip_fetch: bool, wear_limit: int, review_limit: int) -> None:
    if not skip_fetch:
        _show(extract_pbf(RAW / "utrecht-latest.osm.pbf", LAYERS))
    _show(build_candidates(LAYERS, GENERATED / "candidates.geojson"))
    _show(
        score_imagery(
            GENERATED / "candidates.geojson",
            GENERATED / "wear.geojson",
            ROOT / "data" / "cache" / "pdok",
            SITE / "chips",
            limit=wear_limit,
        )
    )
    _show(
        evaluate_models(
            GENERATED / "wear.geojson",
            GENERATED / "scored.geojson",
            GENERATED / "metrics.json",
        )
    )
    _show(
        review_candidates(
            GENERATED / "scored.geojson",
            GENERATED / "reviewed.geojson",
            SITE / "chips",
            limit=review_limit,
        )
    )
    _show(build_walk(GENERATED / "reviewed.geojson", SITE / "downloads"))
    from .site import build_site

    _show(build_site(GENERATED, SITE))


def _show(result: dict) -> None:
    click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

