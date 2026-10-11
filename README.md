# Desire Lines

> Pedestrian pull requests the city never merged.

A desire path is a shortcut worn into grass by repeated footsteps. Desire Lines finds
places where the official pedestrian network takes a detour, checks open aerial imagery
for a continuous loss of vegetation, ranks candidates (TabPFN when its license gate
allows, otherwise sklearn and a transparent heuristic), and optionally asks a local
Gemma vision model for a conservative second opinion.

This project was built for the
[Hacktoberfest Open-Source AI Challenge: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

No field walk has been done. The site can export a GPX and a printable card as an
invitation for a human mapper. The pipeline never writes to OpenStreetMap.

## What it produces

- a map where each candidate looks like a pull request;
- a spatially cross-validated comparison of TabPFN (license-gated) and conventional baselines;
- optional GPX / A6 card / MapRoulette GeoJSON after `desire-lines walk` — not a completed survey;
- no automatic OpenStreetMap edits.

## Pipeline

```text
Geofabrik PBF ──> candidate geometry ──> PDOK aerial wear score
                                               │
mapped informal=yes ──> spatial CV ──> ranker ─┤
                                               ▼
                                      optional Gemma review (Ollama, CPU)
                                               │
                                      static map (no OSM writes)
```

The default study area is Utrecht, Netherlands. It is unusually suitable for a reproducible
demo: desire paths are locally known as *olifantenpaadjes*, the Netherlands publishes
25 cm national orthophotos as open data, and OpenStreetMap contains mapped informal paths
that can serve as imperfect labels.

## Install

Python 3.11 is recommended.

```powershell
conda create -n desire-lines python=3.11 pip
conda activate desire-lines
pip install -e ".[dev,ai]"
```

### TabPFN license gate

`pip install -e ".[ai]"` installs TabPFN, but local weights are license-gated by Prior Labs.
On a non-interactive terminal that surfaces as `TabPFNLicenseError` (no TTY to accept the
agreement). To enable TabPFN:

1. Open https://ux.priorlabs.ai, log in, and accept the license.
2. Copy an API key from https://ux.priorlabs.ai/account
3. Set `TABPFN_TOKEN` before `desire-lines score`.

If the gate is closed, `score` still runs: logistic regression, histogram gradient boosting,
and the detour + wear heuristic. That fallback is expected, not a crash.

### Gemma / Ollama on CPU

Vision review is optional and local. Install [Ollama](https://ollama.com/) and a
vision-capable Gemma model, then run it on CPU — no GPU is required:

```powershell
ollama pull gemma3:4b
```

If Ollama is missing or the model times out, `review` keeps a deterministic fallback so the
map is never empty.

Download the Utrecht extract:

```powershell
Invoke-WebRequest https://download.geofabrik.de/europe/netherlands/utrecht-latest.osm.pbf `
  -OutFile data/raw/utrecht-latest.osm.pbf
```

## Run

Run each cached stage independently:

```powershell
desire-lines fetch
desire-lines predict
desire-lines wear --limit 80
desire-lines score
desire-lines review --limit 20
desire-lines site
```

`desire-lines walk` is optional and only writes local GPX / card / task files. It does not
survey the ground and it does not edit OSM.

Or:

```powershell
desire-lines all
```

Serve the static result:

```powershell
python -m http.server 8080 --directory site
```

Open <http://localhost:8080>.

## How candidates are generated

1. Remove mapped `informal=yes` paths from the walk graph, approximating the formally planned
   network.
2. Collect official path nodes near green-space edges and nearby destinations.
3. Connect pairs 20–400 m apart with a straight line.
4. Keep a line only when at least 80% lies in green space, it crosses no mapped barrier,
   the official network is at least 1.25× longer, and the line saves at least 15 m.
5. Deduplicate lines within 8 m Hausdorff distance.

### Aerial wear signal

For each line, the app compares Excess Green (`2G - R - B`) in a 1.5 m corridor with two
parallel control strips. `wear` is the standardized greenness drop; `continuity` is the
fraction of corridor pixels below the local vegetation threshold. It is only a signal:
shade, dry grass, paths under trees, recent construction, and image age can all fool it.

### Evaluation

A prediction receives a positive label when it aligns within 10 m and 20° of a mapped
`informal=yes` way. Spatial block cross-validation keeps nearby candidates in the same fold.
The benchmark compares:

- TabPFN, when the Prior Labs license gate is open;
- logistic regression;
- histogram gradient boosting;
- a transparent detour + imagery heuristic.

Unmapped desire paths are counted as negatives even though some may be the discoveries we
want. Metrics therefore measure agreement with incomplete OpenStreetMap data—not truth.

## Responsible mapping

No field walk has been completed for these candidates. Do not add a path to OpenStreetMap
from this model or aerial imagery alone. Survey it. Check access, barriers, surface, current
existence, and local mapping conventions. The generated task file says the same thing, and
this project never calls an OSM write API.

## Open data and model attribution

- OpenStreetMap data: © OpenStreetMap contributors, licensed under the ODbL.
- Utrecht `.osm.pbf`: Geofabrik, derived from OpenStreetMap.
- Aerial imagery: Beeldmateriaal.nl / PDOK, CC BY 4.0.
- TabPFN: Prior Labs; local inference requires one-time license acceptance (`TABPFN_TOKEN`).
- Gemma: Google's open-weight model, run locally through Ollama on CPU; see the Gemma terms.

The source code in this repository is MIT licensed. Generated datasets retain the terms of
their source data.

## Tests

```powershell
pytest
ruff check .
```
