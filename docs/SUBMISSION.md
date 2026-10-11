---
title: Desire paths are pull requests the city never merged
published: false
tags: devchallenge, hf26challenge, gemma, tabpfn
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).*

#devchallenge #hf26challenge #gemma #tabpfn

## What I built

In Utrecht a desire path is an *olifantenpaadje*: grass worn off because people cut the corner the pavement took. Desire Lines looks for those cuts inside a fixed bbox, 5.09°E, 52.075°N to 5.155°E, 52.125°N.

The geometry comes from a Geofabrik OpenStreetMap PBF. The pixels come from PDOK, the Dutch 25 cm orthophoto (Beeldmateriaal.nl, CC BY 4.0, layer `Actueel_ortho25`). For each line the app computes Excess Green, `2G - R - B`, inside a 1.5 m corridor and compares it with two parallel control strips. `wear` is the greenness drop, in standard deviations of the control strips. `continuity` is the fraction of corridor pixels under the local vegetation threshold.

The same rows go to TabPFN, logistic regression, and histogram gradient boosting, with spatial block cross-validation. A local Gemma 3 4B model can look at a chip through Ollama and answer yes, no, or unclear. The machine is a CPU-only Windows laptop. It has no NVIDIA GPU, so vLLM and SGLang were not used.

The pipeline does not edit OpenStreetMap. It writes a map, a GPX file, a printable A6 field card, and MapRoulette-style tasks for a person to survey.

I have not walked the route before the deadline.

## Demo

https://desire-lines.vercel.app

The site in this repo is the `site/` directory:

```powershell
python -m http.server 8080 --directory site
```

http://localhost:8080 draws each candidate as a review status, with a PDOK aerial toggle. The field tab links `desire-lines-walk.gpx`, the A6 card, and `maproulette-tasks.geojson`. The card lists eight stops. The first line is a 27 m shortcut printed as saving about 17 seconds. The boxes for worn, faint, gone, and paved are empty.

## Code

The live demo is https://desire-lines.vercel.app. The source is not on a public Git remote yet.

Source code in the repository is MIT. OpenStreetMap data remains ODbL. The Utrecht `.osm.pbf` is Geofabrik's extract of that data. Aerial imagery is Beeldmateriaal.nl / PDOK, CC BY 4.0. TabPFN weights stay under Prior Labs' license (`TABPFN_TOKEN` after a one-time acceptance at https://ux.priorlabs.ai). Gemma is Google's open-weight model. The install note is `ollama pull gemma3:4b`.

```powershell
desire-lines fetch
desire-lines predict
desire-lines wear --limit 80
desire-lines score
desire-lines review --limit 20
desire-lines walk
desire-lines site
```

`desire-lines walk` only writes local files. It does not survey the ground, and it does not call an OSM write API.

## How I built it

### Candidates

Mapped `informal=yes` ways are removed from the walk graph before any detour is measured. What remains is the official pedestrian network. Endpoints are path nodes near green-space edges, plus nearby destinations. Two endpoints become a candidate when the straight line is 20-400 m, at least 80% of it lies in mapped green space, it crosses no mapped barrier, the official walk is at least 1.25× longer, and the line saves at least 15 m. Near-duplicates within 8 m Hausdorff distance are dropped. Seconds saved divide metres saved by 1.3 m/s.

This run found 81 candidates. Wear, scoring, and the map use the top 40.

### Aerial wear

Chips are PDOK tiles at zoom 19. Shade, dry grass, paths under trees, recent construction, and the age of the photo can all move Excess Green. Three of the five mapped informal ways in this extract have negative wear: the corridor is greener than the strips beside it.

`utrecht-080` is the top of `scored.geojson`. It is a mapped informal way, 27.403 m, wear -0.392, continuity 0.204, logistic regression score 0.9927. Wear is negative and it still ranks first. The label matches. The rank does not follow the wear sign.

### Spatial comparison

A predicted line is a positive when its Hausdorff distance to a mapped `informal=yes` way is at most 12 m and the angles agree within 20°. The mapped ways are stored as positives too. Unmapped desire paths are labeled negative. The metrics measure agreement with incomplete OpenStreetMap labels.

Folds are 1 km blocks, five of them (`spatial_folds` in `metrics.json` is 5). Candidates that fall in the same block stay in the same fold. The columns are length, network distance, detour ratio, metres saved, seconds saved, green fraction, wear, and continuity.

`data/generated/metrics.json` for this run:

| Model | ROC-AUC | PR-AUC | Precision at 10 |
| --- | ---: | ---: | ---: |
| logistic regression | 0.9771 | 0.8762 | 0.5 |
| histogram gradient boosting | 0.5 | 0.125 | 0.0 |
| detour + wear heuristic | 0.4029 | 0.1176 | 0.0 |
| TabPFN | no token | n/a | n/a |

Primary model: `logistic_regression`. Samples: 40. Mapped positives: 5. Precision at 10 is the share of the ten highest scores with a positive label, so 0.5 means five of those ten.

TabPFN did not return a score. Local weights need a one-time license acceptance, and this terminal had no `TABPFN_TOKEN` (`TabPFNLicenseError`). The optional TabPFN client had no access token either. Logistic regression, histogram gradient boosting, and the detour + wear heuristic still ran.

All five positives are `source: mapped_informal`. For those rows the code writes detour ratio 1.8, metres saved as 0.8 × length, and seconds as that distance at 1.3 m/s. The 17 seconds on the first card line is that formula on the 27.403 m way (16.864 seconds, rounded on the card).

### Vision review

`review` posts a JPEG chip to Ollama at `http://127.0.0.1:11434`. The prompt asks whether a narrow continuous worn track is visible under the red line. The schema allows `yes`, `no`, or `unclear`. People, intent, safety, and legal status are outside the question. Unclear is the requested answer when trees, shadows, resolution, or pavement block the view. Temperature is 0. The README model is `gemma3:4b`.

Gemma 3 4B reviewed the top 8 chips through Ollama. All 8 verdicts were `unclear`. The other 32 cards remain the deterministic fallback: yes only when wear is at least 1 and continuity is at least 0.55, otherwise unclear.

## Why open matters

Wear is a number computed from pixels. Closed map imagery forbids deriving data from the pictures. PDOK's 25 cm national orthophoto is CC BY 4.0, so the corridor score can be published with the chips.

Gemma 3 4B is an open-weight model run locally through Ollama. The chips are aerial frames of Utrecht parks, and the request goes to `127.0.0.1`. vLLM and SGLang were not used: the laptop has no NVIDIA GPU.

TabPFN is in the scorer as `TabPFNClassifier(device="cpu")`, beside logistic regression and histogram gradient boosting on the same folds. This run hit the Prior Labs license gate. `metrics.json` stores `tabpfn_license_gate` and sets `primary_model` to `logistic_regression`.

## Prize categories

**Best Use of Gemma.** Vision review is a local Ollama call, model `gemma3:4b`, JSON verdicts `yes` / `no` / `unclear`. This run saved 8 Gemma verdicts, all `unclear`.

**Best Use of TabPFN.** Scoring compares TabPFN with logistic regression and histogram gradient boosting under spatial block cross-validation. This run had no `TABPFN_TOKEN` and wrote no TabPFN ROC-AUC. The completed baseline is logistic regression at 0.9771 ROC-AUC, 0.8762 PR-AUC, and 0.5 precision at 10.

## Honest limits

I have not walked the eight stops on the field card. The worn / faint / gone / paved boxes are unticked.

The five positives are mapped `informal=yes` ways. The other 35 scored rows are negatives, unmapped desire paths included. 0.9771 ROC-AUC measures agreement with those labels. On the positive rows the code sets detour ratio to 1.8, metres saved to 0.8 × length, and seconds from that distance at 1.3 m/s.

`utrecht-080` ranks first with wear -0.392 and continuity 0.204.

TabPFN has no ROC-AUC, PR-AUC, or precision at 10 in `metrics.json`.

Gemma 3 4B reviewed 8 chips through Ollama. All 8 verdicts were `unclear`. The other 32 cards remain the deterministic fallback.

The task file says "Survey only. Do not map from imagery alone." No stage calls an OpenStreetMap write API.
