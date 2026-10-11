from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def build_site(generated: Path, site: Path) -> dict[str, Any]:
    site.mkdir(parents=True, exist_ok=True)
    data = site / "data"
    data.mkdir(exist_ok=True)
    reviewed = generated / "reviewed.geojson"
    metrics = generated / "metrics.json"
    if not reviewed.exists():
        raise FileNotFoundError(f"Run `desire-lines review` first: {reviewed}")
    shutil.copyfile(reviewed, data / "desire-lines.geojson")
    if metrics.exists():
        shutil.copyfile(metrics, data / "metrics.json")
    else:
        (data / "metrics.json").write_text("{}", encoding="utf-8")
    payload = json.loads(reviewed.read_text(encoding="utf-8"))
    (site / "index.html").write_text(INDEX, encoding="utf-8")
    (site / "styles.css").write_text(STYLES, encoding="utf-8")
    (site / "app.js").write_text(APP, encoding="utf-8")
    (site / ".nojekyll").write_text("", encoding="utf-8")
    return {"features": len(payload["features"]), "site": str(site)}


INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#e7e3d5">
  <title>Desire Lines — pedestrian pull requests</title>
  <meta name="description" content="Open AI finds pedestrian shortcuts the city never merged.">
  <link rel="preconnect" href="https://unpkg.com">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIINfQ3ynhZ6+K8YtJVpZxJxZ6L0GcA4u3w=" crossorigin="">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <a class="mark" href="#map" aria-label="Desire Lines home">DL<span>↗</span></a>
    <nav aria-label="Primary">
      <button class="nav active" data-tab="map">Map</button>
      <button class="nav" data-tab="walk">Field walk</button>
      <button class="nav" data-tab="evaluation">Evaluation</button>
    </nav>
    <a class="source" href="https://github.com/" rel="noreferrer">Open source</a>
  </header>
  <main>
    <section class="intro">
      <p class="eyebrow">UTRECHT / OPEN AERIAL IMAGERY / LOCAL AI</p>
      <h1 aria-label="Pull requests the city never merged">Pull requests the city<br>never merged.</h1>
      <p class="lede">A desire path is grass touched by so many feet that it becomes a vote.
      We use open maps, open imagery and open models to find those votes—then send people
      outside to check them.</p>
      <div class="stats">
        <div><strong id="candidate-count">—</strong><span>candidates</span></div>
        <div><strong id="confirmed-count">—</strong><span>visible traces</span></div>
        <div><strong id="minutes-saved">—</strong><span>minutes reclaimed</span></div>
      </div>
    </section>

    <section id="map" class="panel active">
      <div class="map-shell">
        <div id="leaflet-map" aria-label="Map of predicted desire paths"></div>
        <aside class="legend">
          <div class="legend-title">REVIEW STATUS</div>
          <label><i class="dot yes"></i> Visible trace</label>
          <label><i class="dot unclear"></i> Needs field check</label>
          <label><i class="dot no"></i> Rejected</label>
          <hr>
          <label class="switch"><input id="imagery" type="checkbox"><span></span> Aerial view</label>
        </aside>
        <article id="pull-request" class="pr-card" hidden>
          <button id="close-pr" aria-label="Close">×</button>
          <p class="eyebrow">PEDESTRIAN PR <span id="pr-id"></span></p>
          <h2 id="pr-title"></h2>
          <pre id="pr-diff"></pre>
          <p id="pr-evidence"></p>
          <div class="pr-meta"><span id="pr-model"></span><span id="pr-score"></span></div>
        </article>
      </div>
      <p class="attribution">© OpenStreetMap contributors, ODbL · Aerial imagery:
      Beeldmateriaal.nl / PDOK, CC BY 4.0. Predictions are not map edits.</p>
    </section>

    <section id="walk" class="panel field">
      <div>
        <p class="eyebrow">THE MODEL STOPS HERE</p>
        <h2>Take the review outside.</h2>
        <p>AI can point at a pale line in a photograph. It cannot tell whether the gate is
        locked, the ground is flooded, or the path still exists today. That is your job.</p>
        <div class="actions">
          <a href="downloads/desire-lines-walk.gpx" download>Download GPX</a>
          <a href="downloads/field-card.html" target="_blank">Print A6 field card</a>
          <a href="downloads/maproulette-tasks.geojson" download>Mapper tasks</a>
        </div>
      </div>
      <ol class="ritual">
        <li><b>01</b><span><strong>Walk</strong>Put the phone away between stops.</span></li>
        <li><b>02</b><span><strong>Look</strong>Mark worn, faint, gone or paved.</span></li>
        <li><b>03</b><span><strong>Map</strong>Edit only what you personally verify.</span></li>
      </ol>
    </section>

    <section id="evaluation" class="panel eval">
      <div>
        <p class="eyebrow">MODEL CARD, NOT MARKETING</p>
        <h2>What did the models actually do?</h2>
        <p>Mapped <code>informal=yes</code> paths are useful labels, but incomplete ones.
        A supposed false positive may be the unmapped path we are trying to discover.
        Spatial folds keep nearby examples out of both training and test sets.</p>
      </div>
      <div id="metrics" class="metrics"></div>
    </section>
  </main>
  <footer><span>DESIRE LINES, 2026</span><span>No automatic OSM edits. Human survey required.</span></footer>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script src="app.js"></script>
</body>
</html>
"""

STYLES = r"""@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;600;700&display=swap');
:root{--ink:#172019;--paper:#e8e4d8;--lime:#d7ff3f;--coral:#ff5e48;--muted:#64695f;--line:#a5aa9b}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:Manrope,system-ui,sans-serif}
header{height:72px;padding:0 4vw;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:1000;background:rgba(232,228,216,.94);backdrop-filter:blur(10px)}
.mark{font:700 22px DM Mono;color:var(--ink);text-decoration:none}.mark span{color:var(--coral)}nav{display:flex;gap:5px}.nav{font:500 12px DM Mono;text-transform:uppercase;border:0;background:transparent;padding:10px 14px;cursor:pointer}.nav.active{background:var(--ink);color:var(--paper)}.source{font:500 12px DM Mono;color:var(--ink)}
main{max-width:1500px;margin:auto}.intro{padding:8vh 5vw 6vh;display:grid;grid-template-columns:1fr minmax(270px,470px);gap:3vw}.eyebrow{font:500 11px DM Mono;letter-spacing:.1em}.intro .eyebrow{grid-column:1/-1}.intro h1{font-size:clamp(46px,7vw,108px);line-height:.9;letter-spacing:-.065em;margin:0}.lede{font-size:clamp(16px,1.5vw,22px);line-height:1.55;margin:2vh 0 0}.stats{grid-column:1/-1;display:flex;border-top:1px solid var(--line);margin-top:4vh}.stats div{min-width:180px;padding:18px 32px 0 0}.stats strong{font:500 32px DM Mono;display:block}.stats span{font:11px DM Mono;text-transform:uppercase;color:var(--muted)}
.panel{display:none;padding:0 4vw 7vh}.panel.active{display:block}.map-shell{height:68vh;min-height:550px;position:relative;border:1px solid var(--ink);background:#cad2c3;overflow:hidden}#leaflet-map{height:100%}.leaflet-tile{filter:saturate(.65) contrast(.92)}.legend{position:absolute;left:18px;bottom:18px;z-index:500;background:var(--paper);border:1px solid var(--ink);padding:15px;width:190px;box-shadow:5px 5px 0 var(--ink);font:11px DM Mono}.legend-title{margin-bottom:9px}.legend label{display:block;margin:7px 0}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:7px}.dot.yes{background:var(--coral)}.dot.unclear{background:#ecb833}.dot.no{background:#788078}.legend hr{border:0;border-top:1px solid var(--line);margin:12px 0}.switch input{margin:0 7px 0 0}
.pr-card{position:absolute;z-index:600;right:18px;top:18px;width:min(390px,calc(100% - 36px));background:var(--ink);color:var(--paper);padding:24px;box-shadow:8px 8px 0 var(--lime)}.pr-card h2{font-size:25px;line-height:1.08;margin:12px 0}.pr-card pre{white-space:pre-wrap;background:#263029;border-left:3px solid var(--lime);padding:13px;color:var(--lime);font:12px DM Mono}.pr-card button{position:absolute;right:13px;top:10px;border:0;background:none;color:var(--paper);font-size:25px;cursor:pointer}.pr-card p{line-height:1.55}.pr-meta{display:flex;justify-content:space-between;border-top:1px solid #485149;padding-top:12px;font:10px DM Mono}.attribution{font:10px DM Mono;color:var(--muted)}
.field,.eval{min-height:620px;padding-top:8vh!important;grid-template-columns:1fr 1fr;gap:8vw}.field.active,.eval.active{display:grid}.field h2,.eval h2{font-size:clamp(40px,5vw,74px);line-height:.96;letter-spacing:-.05em;margin:13px 0 30px}.field p,.eval p{font-size:18px;line-height:1.6}.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:35px}.actions a{background:var(--ink);color:var(--paper);font:12px DM Mono;padding:14px 17px;text-decoration:none}.actions a:first-child{background:var(--coral);color:var(--ink)}.ritual{list-style:none;margin:0;padding:0}.ritual li{display:flex;gap:25px;border-top:1px solid var(--ink);padding:24px 0}.ritual b{font:30px DM Mono;color:var(--coral)}.ritual span{line-height:1.5}.ritual strong{display:block;font-size:28px}.metrics{font:12px DM Mono;border-top:4px solid var(--ink)}.metric{display:grid;grid-template-columns:1fr auto;border-bottom:1px solid var(--line);padding:16px 0}.metric strong{font-size:18px}.bar{grid-column:1/-1;height:5px;background:#c3c4b7;margin-top:10px}.bar i{display:block;height:100%;background:var(--coral)}
footer{border-top:1px solid var(--line);padding:25px 4vw;display:flex;justify-content:space-between;font:10px DM Mono}
@media(max-width:760px){header{padding:0 15px}.source{display:none}.nav{padding:8px}.intro{display:block;padding:6vh 20px}.intro h1{margin:20px 0}.stats{overflow:auto}.stats div{min-width:130px}.panel{padding-left:14px;padding-right:14px}.map-shell{height:74vh}.legend{display:none}.field.active,.eval.active{display:block}.ritual,.metrics{margin-top:55px}footer{gap:20px}.pr-card{top:auto;bottom:18px}}
@media print{header,.intro,.legend,.pr-card,footer{display:none}.panel{display:block!important}.map-shell{height:90vh}}
"""

APP = r"""const tabs=[...document.querySelectorAll('.nav')];
tabs.forEach(b=>b.addEventListener('click',()=>{tabs.forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));document.getElementById(b.dataset.tab).classList.add('active');if(b.dataset.tab==='map')setTimeout(()=>map.invalidateSize(),0)}));
const map=L.map('leaflet-map',{zoomControl:false}).setView([52.09,5.12],13);L.control.zoom({position:'bottomright'}).addTo(map);
const osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'© OpenStreetMap contributors'}).addTo(map);
const aerial=L.tileLayer('https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=Actueel_ortho25&STYLE=&FORMAT=image/jpeg&tileMatrixSet=EPSG:3857&tileMatrix={z}&tileRow={y}&tileCol={x}',{maxZoom:20,attribution:'Beeldmateriaal.nl / PDOK, CC BY 4.0'});
document.getElementById('imagery').addEventListener('change',e=>e.target.checked?(map.removeLayer(osm),aerial.addTo(map)):(map.removeLayer(aerial),osm.addTo(map)));
const colors={yes:'#ff5e48',unclear:'#ecb833',no:'#788078'};
function openPR(f){const p=f.properties,r=p.review||{};document.getElementById('pull-request').hidden=false;document.getElementById('pr-id').textContent='#'+p.id;document.getElementById('pr-title').textContent=r.title||'Field check needed';document.getElementById('pr-diff').textContent=r.diff||'+'+Math.round(p.length_m)+' m candidate';document.getElementById('pr-evidence').textContent=r.evidence||'No model review available.';document.getElementById('pr-model').textContent=r.source||p.model||'heuristic';document.getElementById('pr-score').textContent='score '+Math.round((p.score||0)*100)+'%'}
document.getElementById('close-pr').onclick=()=>document.getElementById('pull-request').hidden=true;
Promise.all([fetch('data/desire-lines.geojson').then(r=>r.json()),fetch('data/metrics.json').then(r=>r.json())]).then(([geo,metrics])=>{
 const bounds=[];let confirmed=0,seconds=0;geo.features.forEach(f=>{const p=f.properties,r=p.review||{},v=r.verdict||'unclear';if(v==='yes'){confirmed++;seconds+=p.seconds_saved||0}const layer=L.geoJSON(f,{style:{color:colors[v],weight:v==='yes'?6:4,opacity:.9,dashArray:v==='unclear'?'8 7':null}}).on('click',()=>openPR(f)).addTo(map);bounds.push(layer.getBounds())});
 document.getElementById('candidate-count').textContent=geo.features.length;document.getElementById('confirmed-count').textContent=confirmed;document.getElementById('minutes-saved').textContent=Math.round(seconds/60);if(bounds.length){const all=bounds.reduce((a,b)=>a.extend(b));map.fitBounds(all.pad(.12))}
 const rows=[];rows.push(['Samples',metrics.samples||0,1]);rows.push(['Mapped positives',metrics.positives||0,(metrics.positives||0)/(metrics.samples||1)]);Object.entries(metrics.models||{}).forEach(([name,m])=>{if(m.roc_auc!==undefined)rows.push([name+' ROC-AUC',m.roc_auc,m.roc_auc]);if(m.pr_auc!==undefined)rows.push([name+' PR-AUC',m.pr_auc,m.pr_auc])});document.getElementById('metrics').innerHTML=rows.map(([n,v,w])=>`<div class="metric"><span>${n.replaceAll('_',' ')}</span><strong>${typeof v==='number'&&v<1?v.toFixed(3):v}</strong><div class="bar"><i style="width:${Math.min(100,w*100)}%"></i></div></div>`).join('')
}).catch(e=>{console.error(e);document.getElementById('candidate-count').textContent='0'});
"""

