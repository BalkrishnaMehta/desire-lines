---
title: Desire paths are pull requests the city never merged
published: false
tags: devchallenge, hf26challenge, gemma, tabpfn
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).*

#devchallenge #hf26challenge #gemma #tabpfn

## What I Built <!-- hw-ignore -->

In Utrecht a desire path is an *olifantenpaadje*: grass worn off because people cut the corner the pavement took. The official walk is already on the map. The shortcut is the line the map never accepted.

Desire Lines looks for those cuts inside one box, 5.09°E, 52.075°N to 5.155°E, 52.125°N. Geometry comes from a Geofabrik OpenStreetMap extract. The pixels come from PDOK, the Dutch 25 cm orthophoto. A local Gemma model looks at each aerial chip and answers yes, no, or unclear. The pipeline writes a map, a GPX file, a printable field card, and mapper tasks. I have not walked the route. Nothing is written to OpenStreetMap.

## Demo

https://desire-lines.vercel.app

{% embed https://desire-lines.vercel.app %}

The map is central Utrecht. It draws 40 candidates. Click a line and a card opens with the length, the seconds that detour would save, the wear number, and a verdict.

The field tab links a GPX file, an A6 card, and mapper tasks. The card lists eight stops. The boxes for worn, faint, gone, and paved are empty.

## Code

https://github.com/BalkrishnaMehta/desire-lines/

{% github BalkrishnaMehta/desire-lines %}

Source code is MIT. OpenStreetMap data remains ODbL. Aerial imagery is Beeldmateriaal.nl / PDOK, CC BY 4.0. TabPFN weights stay under Prior Labs' license. Gemma is Google's open-weight model. The local install was `ollama pull gemma3:4b`.

## How I Built It <!-- hw-ignore -->

Mapped `informal=yes` ways are removed from the walk graph before any detour is measured. A pair becomes a candidate when the straight line is 20–400 m, at least 80% of it lies in mapped green space, it crosses no mapped barrier, the official walk is at least 1.25× longer, and the line saves at least 15 m.

This run found 81 candidates. Wear, scoring, and the map use the top 40.

For each line the app computes Excess Green, `2G - R - B`, inside a 1.5 m corridor and compares it with two parallel control strips. `wear` is the greenness drop, in standard deviations of those strips. `continuity` is the share of corridor pixels under the local vegetation threshold. Shade, dry grass, trees, and the age of the photo can move that number.

A line is a positive when its Hausdorff distance to a mapped `informal=yes` way is at most 12 m and the angles agree within 20°. Unmapped desire paths are labeled negative. Folds are 1 km blocks, five of them. Candidates in the same block stay in the same fold.

| Model | ROC-AUC | PR-AUC | Precision at 10 |
| --- | ---: | ---: | ---: |
| logistic regression | 0.9771 | 0.8762 | 0.5 |
| histogram gradient boosting | 0.5 | 0.125 | 0.0 |
| detour + wear heuristic | 0.4029 | 0.1176 | 0.0 |
| TabPFN | no token | n/a | n/a |

Logistic regression is the measured model. Samples: 40. Mapped positives: 5. TabPFN returned no score. This machine had no `TABPFN_TOKEN`.

`utrecht-080` ranks first. It is a mapped informal way, 27.403 m, wear -0.392, continuity 0.204, score 0.9927. The corridor is greener than the grass beside it.

The five positives are stored with a filled-in detour. The code writes detour ratio 1.8, metres saved as 0.8 × length, and seconds as that distance at 1.3 m/s. The 0.9771 ROC-AUC is agreement with those labels.

Gemma 3 4B reviewed the top 8 chips through Ollama at `http://127.0.0.1:11434`. The laptop is a CPU-only Windows machine with no NVIDIA GPU. The prompt asks whether a narrow worn track is visible under the red line. All 8 verdicts were `unclear`. The other 32 cards use a fallback that says yes only when wear is at least 1 and continuity is at least 0.55.

## Why Does Open Innovation Matter? <!-- hw-ignore -->

PDOK publishes the national 25 cm orthophoto under CC BY 4.0, layer `Actueel_ortho25`. That license allows a published measurement from the pixels, so the corridor score and the chips can sit in the repository.

The chips are aerial frames of Utrecht parks. Gemma ran on the laptop. The request went to `127.0.0.1`.

## Prize categories

**Best Use of Gemma.** Local Ollama, model `gemma3:4b`, verdicts `yes`, `no`, or `unclear`. This run saved 8 Gemma verdicts, all `unclear`.

**Best Use of TabPFN.** The scorer calls `TabPFNClassifier` on the same spatial folds as logistic regression and histogram gradient boosting. This run had no token and no TabPFN ROC-AUC.

## Honest limits

I have not walked the eight stops. The worn, faint, gone, and paved boxes are unticked.

The task file says to survey a line before mapping it. No stage calls an OpenStreetMap write API.
