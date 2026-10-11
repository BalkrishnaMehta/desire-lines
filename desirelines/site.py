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
    vendor = Path(__file__).resolve().parent / "vendor"
    if vendor.exists():
        shutil.copytree(vendor, site / "vendor", dirs_exist_ok=True)
    return {"features": len(payload["features"]), "site": str(site)}


INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#17352e">
  <title>Desire Lines — pedestrian pull requests</title>
  <meta name="description" content="Open AI finds pedestrian shortcuts the city never merged.">
  <link rel="preconnect" href="https://unpkg.com">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="vendor/leaflet.css">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip" href="#leaflet-map">Skip to map</a>
  <div class="sheet">
    <header>
      <a class="mark" href="#map" aria-label="Desire Lines home">Desire Lines</a>
      <nav class="tabs" role="tablist" aria-label="Primary">
        <button class="nav active" role="tab" aria-selected="true" aria-controls="map" id="tab-map" data-tab="map">Map</button>
        <button class="nav" role="tab" aria-selected="false" aria-controls="walk" id="tab-walk" data-tab="walk">Field walk</button>
        <button class="nav" role="tab" aria-selected="false" aria-controls="evaluation" id="tab-evaluation" data-tab="evaluation">Evaluation</button>
      </nav>
      <a class="source" href="https://dev.to/challenges/hacktoberfest-week1-2026-10-05" rel="noreferrer">Challenge</a>
    </header>
    <main>
      <section id="map" class="panel active" role="tabpanel" aria-labelledby="tab-map">
        <div class="map-layout">
          <div class="titleblock">
            <p class="sheet-id">Utrecht sheet, open aerial imagery</p>
            <h1>Pull requests the city never merged.</h1>
            <p class="lede">A desire path is grass touched by so many feet that it becomes a vote.
            We use open maps, open imagery and open models to find those votes. Nothing is written
            to OpenStreetMap. No field walk has been done.</p>
            <div class="stats">
              <div><span>Candidates</span><strong id="candidate-count">—</strong></div>
              <div><span>Needs field check</span><strong id="check-count">—</strong></div>
              <div><span>Longest shortcut</span><strong id="longest-shortcut">—</strong></div>
            </div>
          </div>
          <div class="map-shell">
            <div id="leaflet-map" aria-label="Map of predicted desire paths"></div>
            <article id="pull-request" class="pr-card" hidden>
              <button id="close-pr" type="button" aria-label="Close pull request">×</button>
              <p class="kicker">Pedestrian pull request <span id="pr-id"></span>
                <span id="pr-verdict" class="badge"></span></p>
              <h2 id="pr-title"></h2>
              <pre id="pr-diff"></pre>
              <p id="pr-evidence"></p>
              <p id="pr-action"></p>
              <div class="pr-signals">
                <span id="pr-wear"></span>
                <span id="pr-continuity"></span>
              </div>
              <div class="pr-meta"><span id="pr-model"></span><span id="pr-score"></span></div>
            </article>
            <aside class="legend">
              <div class="legend-title">Review status</div>
              <div class="key"><i class="swatch yes" aria-hidden="true"></i> Visible trace</div>
              <div class="key"><i class="swatch unclear" aria-hidden="true"></i> Needs field check</div>
              <div class="key"><i class="swatch no" aria-hidden="true"></i> Rejected</div>
              <hr>
              <label class="switch" for="pdok-toggle">
                <input id="pdok-toggle" type="checkbox" role="switch" aria-checked="false">
                <span class="track" aria-hidden="true"></span>
                PDOK aerial
              </label>
            </aside>
          </div>
        </div>
        <p class="attribution">© OpenStreetMap contributors, ODbL. Aerial imagery:
        Beeldmateriaal.nl / PDOK, CC BY 4.0. Predictions are not map edits.</p>
      </section>

      <section id="walk" class="panel field" role="tabpanel" aria-labelledby="tab-walk" hidden>
        <div class="prose">
          <h2>No field walk has been done.</h2>
          <p>AI can point at a pale line in a photograph. It cannot tell whether the gate is
          locked, the ground is flooded, or the path still exists today. These files are an
          invitation, not a survey record. Nothing is written to OpenStreetMap.</p>
          <div class="actions">
            <a href="downloads/desire-lines-walk.gpx" download>Download GPX</a>
            <a href="downloads/field-card.html" target="_blank" rel="noreferrer">Print A6 field card</a>
            <a href="downloads/maproulette-tasks.geojson" download>Mapper tasks</a>
          </div>
        </div>
        <ol class="ritual">
          <li><b>1</b><span><strong>Walk</strong>Put the phone away between stops.</span></li>
          <li><b>2</b><span><strong>Look</strong>Mark worn, faint, gone or paved.</span></li>
          <li><b>3</b><span><strong>Map</strong>Edit only what you personally verify.</span></li>
        </ol>
      </section>

      <section id="evaluation" class="panel eval" role="tabpanel" aria-labelledby="tab-evaluation" hidden>
        <div class="prose">
          <h2>What did the models actually do?</h2>
          <p>Mapped <code>informal=yes</code> paths are useful labels, but incomplete ones.
          A supposed false positive may be the unmapped path we are trying to discover.
          Spatial folds keep nearby examples out of both training and test sets. TabPFN is
          license-gated; Gemma review runs locally on CPU through Ollama when available.</p>
          <p class="primary-model" id="primary-model"></p>
        </div>
        <div id="metrics" class="metrics"></div>
      </section>
    </main>
    <footer><span>Desire Lines, 2026</span><span>No automatic OSM edits. Human survey required.</span></footer>
  </div>
  <script src="vendor/leaflet.js"></script>
  <script src="app.js"></script>
</body>
</html>
"""

STYLES = r"""@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,500;1,6..72,600&display=swap');
:root{
  --blotter:#17352e;
  --manila:#f1e6cf;
  --slip:#f7f3e8;
  --ink:#1a1714;
  --sienna:#8f2d1c;
  --prussian:#1d4e79;
  --graphite:#4f4a43;
  --rule:#d3c6ae;
  --tab:#e5d6b4;
  color-scheme:light;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;
  min-height:100vh;
  background:var(--blotter);
  color:var(--ink);
  font-family:Newsreader,"Iowan Old Style",Palatino,"Palatino Linotype",serif;
  font-size:18px;
  line-height:1.5;
  overflow-x:hidden;
}
h1,h2,p{margin:0}
a{color:inherit}
::selection{background:#e7cbb8;color:var(--ink)}
.skip{position:absolute;left:-999px;top:8px;z-index:2000;background:var(--manila);color:var(--ink);padding:8px 12px;font-family:"Barlow Condensed",sans-serif}
.skip:focus{left:8px}
:focus-visible{outline:3px solid var(--prussian);outline-offset:3px}
.sheet{
  max-width:1480px;
  margin:22px auto;
  background:var(--manila);
  border:2px solid var(--ink);
  box-shadow:0 0 0 6px var(--manila),0 0 0 7px var(--ink),0 18px 36px rgba(10,20,16,.4);
}
header{
  display:grid;
  grid-template-columns:1fr auto 1fr;
  align-items:end;
  gap:16px;
  padding:16px 18px 0;
  background:var(--manila);
  border-bottom:1px solid var(--ink);
}
.mark{
  justify-self:start;
  margin-bottom:12px;
  font-family:Newsreader,serif;
  font-style:italic;
  font-weight:600;
  font-size:22px;
  text-decoration:none;
  white-space:nowrap;
}
.source{
  justify-self:end;
  margin-bottom:12px;
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:17px;
  text-decoration:underline;
  text-underline-offset:3px;
  white-space:nowrap;
}
.tabs{display:flex;align-items:flex-end;gap:4px}
.nav{
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:17px;
  letter-spacing:.01em;
  border:1px solid var(--ink);
  border-bottom:none;
  background:var(--tab);
  color:var(--ink);
  padding:8px 16px;
  min-height:44px;
  cursor:pointer;
}
.nav.active{background:var(--manila);box-shadow:0 1px 0 var(--manila)}
.nav:hover{background:#efe2c4}
.nav.active:hover{background:var(--manila)}
.panel{display:none}
.panel.active{display:block}
.panel[hidden]{display:none !important}
.map-layout{
  display:grid;
  grid-template-columns:minmax(280px,360px) minmax(0,1fr);
  align-items:stretch;
  min-height:72vh;
}
.titleblock{
  display:flex;
  flex-direction:column;
  padding:28px 26px 22px;
  border-right:1px solid var(--ink);
}
.sheet-id{
  margin:0 0 12px;
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:16px;
  color:var(--graphite);
}
.titleblock h1{
  font-weight:500;
  font-style:italic;
  font-size:clamp(34px,3.2vw,48px);
  line-height:1.05;
  letter-spacing:-.02em;
  text-wrap:balance;
}
.lede{margin-top:14px;font-size:17px;line-height:1.5}
.stats{margin-top:auto;padding-top:22px}
.stats div{
  display:flex;
  justify-content:space-between;
  align-items:baseline;
  gap:12px;
  border-top:1px solid var(--ink);
  padding:7px 0;
}
.stats span{font-family:"Barlow Condensed",sans-serif;font-weight:600;font-size:16px}
.stats strong{font-weight:500;font-size:26px;font-variant-numeric:lining-nums}
.map-shell{position:relative;height:72vh;min-height:560px;overflow:hidden;background:#d7d0c2}
#leaflet-map{position:absolute;inset:0;width:100%;height:100%}
.leaflet-container{width:100%;height:100%;overflow:hidden;font-family:"Barlow Condensed",sans-serif;background:#d7d0c2}
.leaflet-container,.leaflet-container *{box-sizing:content-box}
.leaflet-container img,img.leaflet-tile{max-width:none !important;max-height:none !important;padding:0 !important}
.leaflet-tile-pane{filter:saturate(.45) contrast(1.05) brightness(1.04)}
.aerial-on .leaflet-tile-pane{filter:none}
.leaflet-control-attribution{
  font-family:"Barlow Condensed",sans-serif !important;
  font-size:12px !important;
  background:rgba(241,230,207,.92) !important;
  color:var(--graphite) !important;
}
.leaflet-bar{border:1px solid var(--ink) !important;box-shadow:none !important}
.leaflet-bar a{
  background:var(--manila) !important;
  color:var(--ink) !important;
  border-bottom:1px solid var(--ink) !important;
  width:30px !important;
  height:30px !important;
  line-height:30px !important;
}
.leaflet-bar a:hover{background:var(--tab) !important}
.legend{
  position:absolute;
  left:12px;
  bottom:12px;
  z-index:500;
  width:220px;
  padding:12px 14px;
  background:rgba(241,230,207,.94);
  border:1px solid var(--ink);
}
.legend-title{
  margin-bottom:8px;
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:16px;
}
.key{
  display:flex;
  align-items:center;
  gap:8px;
  margin:6px 0;
  font-family:"Barlow Condensed",sans-serif;
  font-size:16px;
}
.swatch{width:26px;height:4px;flex:0 0 26px;background:var(--graphite)}
.swatch.yes{background:var(--sienna)}
.swatch.unclear{height:0;box-sizing:content-box;background:transparent;border-top:3px dashed var(--prussian)}
.swatch.no{height:3px;background:var(--graphite)}
.legend hr{border:0;border-top:1px solid var(--rule);margin:10px 0}
.switch{
  position:relative;
  display:flex;
  align-items:center;
  gap:10px;
  min-height:44px;
  cursor:pointer;
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:16px;
}
.switch input{position:absolute;left:0;top:8px;opacity:0;width:1px;height:1px}
.track{width:18px;height:18px;border:1.5px solid var(--ink);position:relative;flex:0 0 auto;background:transparent}
.track:after{
  content:"";
  position:absolute;
  left:5px;
  top:1px;
  width:5px;
  height:9px;
  border:solid var(--manila);
  border-width:0 2px 2px 0;
  transform:rotate(45deg);
  opacity:0;
}
.switch input:checked + .track{background:var(--ink)}
.switch input:checked + .track:after{opacity:1}
.switch input:focus-visible + .track{outline:3px solid var(--prussian);outline-offset:3px}
.pr-card{
  position:absolute;
  z-index:600;
  top:14px;
  right:14px;
  width:min(340px,calc(100% - 28px));
  max-height:calc(100% - 28px);
  overflow:auto;
  background:var(--slip);
  color:var(--ink);
  border:1px solid var(--ink);
  border-left:4px solid var(--sienna);
  padding:16px 16px 14px;
  box-shadow:0 14px 30px rgba(26,23,20,.22);
}
.pr-card[hidden]{display:none !important}
.pr-card button{
  position:absolute;
  right:4px;
  top:4px;
  border:0;
  background:transparent;
  color:var(--ink);
  font-family:"Barlow Condensed",sans-serif;
  font-size:28px;
  line-height:1;
  cursor:pointer;
  min-width:44px;
  min-height:44px;
}
.kicker{
  margin:0 36px 8px 0;
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:16px;
}
.pr-card h2{
  font-weight:500;
  font-size:26px;
  line-height:1.15;
  margin:0 0 12px;
}
.pr-card pre{
  white-space:pre-wrap;
  margin:0 0 12px;
  padding:0 0 0 12px;
  border-left:2px solid var(--sienna);
  background:transparent;
  color:var(--sienna);
  font-family:Newsreader,serif;
  font-style:italic;
  font-size:16px;
  line-height:1.45;
}
.pr-card p{line-height:1.5;font-size:16px}
.pr-card p + p{margin-top:8px}
.badge{
  display:inline-block;
  margin-left:8px;
  padding:0 6px;
  border:1px solid currentColor;
  font-size:14px;
  font-weight:600;
}
.badge.yes{color:var(--sienna)}
.badge.unclear{color:var(--prussian)}
.badge.no{color:var(--graphite)}
.pr-signals,.pr-meta{
  display:flex;
  justify-content:space-between;
  gap:12px;
  font-family:"Barlow Condensed",sans-serif;
  font-size:16px;
}
.pr-signals{color:var(--graphite);margin:12px 0}
.pr-meta{border-top:1px solid var(--rule);padding-top:10px}
.attribution{
  margin:0;
  padding:10px 18px 14px;
  font-family:"Barlow Condensed",sans-serif;
  font-size:15px;
  color:var(--graphite);
}
.field.active,.eval.active{
  display:grid;
  grid-template-columns:minmax(0,1.15fr) minmax(280px,.85fr);
}
.prose{padding:36px 32px 40px}
.field h2,.eval h2{
  font-weight:500;
  font-size:clamp(32px,4vw,48px);
  line-height:1.08;
  letter-spacing:-.02em;
  max-width:18ch;
  text-wrap:balance;
}
.prose p{margin-top:14px;font-size:18px;line-height:1.55;max-width:58ch}
code{font-family:"Barlow Condensed",sans-serif;font-size:1.05em;font-weight:600}
.actions{
  display:flex;
  flex-direction:column;
  align-items:stretch;
  max-width:360px;
  margin-top:28px;
  border-top:1px solid var(--ink);
}
.actions a{
  display:flex;
  align-items:center;
  min-height:44px;
  padding:8px 0;
  border-bottom:1px solid var(--rule);
  text-decoration:none;
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:18px;
}
.actions a:before{content:"";width:18px;height:2px;margin-right:10px;background:var(--sienna);flex:0 0 auto}
.actions a:hover{color:var(--sienna)}
.ritual,.metrics{
  margin:0;
  padding:36px 32px 40px;
  border-left:1px solid var(--ink);
}
.ritual{list-style:none}
.ritual li{
  display:grid;
  grid-template-columns:32px 1fr;
  gap:12px;
  border-top:1px solid var(--rule);
  padding:16px 0;
}
.ritual b{
  font-family:"Barlow Condensed",sans-serif;
  font-weight:600;
  font-size:22px;
  color:var(--sienna);
}
.ritual strong{display:block;font-weight:600;font-size:22px}
.ritual span{line-height:1.45}
.primary-model{
  font-family:"Barlow Condensed",sans-serif;
  font-size:17px;
  margin-top:22px;
  padding-top:12px;
  border-top:1px solid var(--rule);
  max-width:58ch;
}
.primary-model:empty{display:none}
.metrics{font-family:"Barlow Condensed",sans-serif;font-size:17px}
.metric{
  display:grid;
  grid-template-columns:1fr auto;
  gap:8px 16px;
  border-bottom:1px solid var(--rule);
  padding:12px 0;
}
.metric strong{font-weight:600;font-size:22px;font-variant-numeric:lining-nums}
.metric.error{grid-template-columns:1fr}
.metric.error strong{font-size:16px;font-weight:500;color:var(--sienna);text-align:left}
.bar{grid-column:1/-1;height:3px;background:rgba(26,23,20,.12)}
.bar i{display:block;height:100%;background:var(--prussian)}
.gate{border-left:3px solid var(--sienna);padding:4px 0 12px 12px;margin-bottom:8px}
.gate strong{font-weight:600;font-size:18px}
.gate p{margin:6px 0 0;font-family:Newsreader,serif;font-size:16px;line-height:1.5;max-width:48ch}
footer{
  display:flex;
  justify-content:space-between;
  gap:16px;
  flex-wrap:wrap;
  border-top:1px solid var(--ink);
  padding:12px 18px 14px;
  font-family:"Barlow Condensed",sans-serif;
  font-size:16px;
}
@media(max-width:900px){
  .sheet{margin:10px}
  header{display:flex;flex-wrap:wrap;align-items:flex-end;padding:12px 12px 0}
  .mark{margin-right:auto}
  .source{display:none}
  .tabs{order:3;width:100%}
  .nav{flex:1;padding:8px 6px}
  .map-layout{display:block;min-height:0}
  .titleblock{border-right:0;border-bottom:1px solid var(--ink);padding:20px 14px 16px}
  .stats{margin-top:22px}
  .map-shell{display:block;height:auto;min-height:0;overflow:visible}
  #leaflet-map{position:relative;inset:auto;width:100%;height:68vh;min-height:420px}
  .legend{
    position:static;
    width:auto;
    display:flex;
    flex-wrap:wrap;
    gap:4px 16px;
    border:none;
    border-top:1px solid var(--ink);
  }
  .legend-title,.switch,.legend hr{width:100%}
  .pr-card{position:static;width:auto;max-height:none;box-shadow:none}
  .field.active,.eval.active{display:block}
  .prose,.ritual,.metrics{padding:24px 14px 28px}
  .ritual,.metrics{border-left:none;border-top:1px solid var(--ink)}
  footer{padding:12px 14px}
}
@media print{
  body{background:#fff;overflow:visible}
  .sheet{margin:0;max-width:none;border:none;box-shadow:none}
  header,footer,.skip,.pr-card,.leaflet-control-zoom,.source,.switch{display:none !important}
  .panel{display:none !important}
  .panel.active{display:block !important}
  .map-layout{display:block !important}
  .titleblock{border:none;padding:0 0 8px}
  .lede,.stats{display:none}
  .titleblock h1{font-size:22px}
  .map-shell{height:auto;min-height:0;display:block;overflow:visible}
  #leaflet-map{position:relative;inset:auto;width:100%;height:78vh;min-height:0}
  .leaflet-tile-pane{filter:none !important}
  .legend{position:static;width:auto;box-shadow:none;print-color-adjust:exact;-webkit-print-color-adjust:exact}
  .swatch{print-color-adjust:exact;-webkit-print-color-adjust:exact}
  .ritual,.metrics{border-left:none}
  a[href^="downloads/"]::after{content:" (" attr(href) ")";font-size:12px}
}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
}
"""

APP = r"""const tabs=[...document.querySelectorAll('.nav')];
const panels=[...document.querySelectorAll('.panel')];
function showTab(name){
  tabs.forEach(x=>{
    const on=x.dataset.tab===name;
    x.classList.toggle('active',on);
    x.setAttribute('aria-selected',on?'true':'false');
  });
  panels.forEach(x=>{
    const on=x.id===name;
    x.classList.toggle('active',on);
    x.hidden=!on;
  });
  if(name==='map')setTimeout(frameMap,0);
}
tabs.forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab)));
document.querySelector('.tabs').addEventListener('keydown',e=>{
  const keys={ArrowRight:1,ArrowLeft:-1};
  if(!(e.key in keys))return;
  const i=tabs.indexOf(document.activeElement);
  if(i<0)return;
  e.preventDefault();
  const next=tabs[(i+keys[e.key]+tabs.length)%tabs.length];
  next.focus();
  showTab(next.dataset.tab);
});
document.querySelector('.mark').addEventListener('click',e=>{
  e.preventDefault();
  showTab('map');
});
document.querySelector('.skip').addEventListener('click',()=>showTab('map'));

const map=L.map('leaflet-map',{zoomControl:false,attributionControl:true}).setView([52.09,5.12],15);
let lineBounds=null;
function frameMap(){
  map.invalidateSize({pan:false});
  if(lineBounds) map.fitBounds(lineBounds,{padding:[28,28],maxZoom:17});
}
L.control.zoom({position:'topleft'}).addTo(map);
map.attributionControl.setPrefix('');
map.attributionControl.addAttribution('© OpenStreetMap contributors, ODbL');
map.attributionControl.addAttribution('Aerial: Beeldmateriaal.nl / PDOK, CC BY 4.0');

const osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:''}).addTo(map);
const aerial=L.tileLayer('https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=Actueel_ortho25&STYLE=&FORMAT=image/jpeg&tileMatrixSet=EPSG:3857&tileMatrix={z}&tileRow={y}&tileCol={x}',{maxZoom:20,attribution:''});
const pdok=document.getElementById('pdok-toggle');
const mapEl=document.getElementById('leaflet-map');
pdok.addEventListener('change',()=>{
  pdok.setAttribute('aria-checked',pdok.checked?'true':'false');
  if(pdok.checked){map.removeLayer(osm);aerial.addTo(map);mapEl.classList.add('aerial-on')}
  else{map.removeLayer(aerial);osm.addTo(map);mapEl.classList.remove('aerial-on')}
});

const colors={yes:'#8f2d1c',unclear:'#1d4e79',no:'#4a463f'};
function fmt(n,digits){return Number.isFinite(n)?n.toFixed(digits):'—'}
function openPR(f){
  const p=f.properties||{};
  const r=p.review||{};
  const length=Math.round(p.length_m||0);
  const saved=Math.round(p.seconds_saved||0);
  const verdict=r.verdict||'unclear';
  const card=document.getElementById('pull-request');
  card.hidden=false;
  if(window.matchMedia('(max-width:900px)').matches){
    card.scrollIntoView({block:'nearest',behavior:window.matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});
  }
  document.getElementById('pr-id').textContent='#'+(p.id||'');
  const badge=document.getElementById('pr-verdict');
  badge.textContent=verdict;
  badge.className='badge '+verdict;
  document.getElementById('pr-title').textContent=r.title||('Formalise '+length+' m pedestrian shortcut');
  document.getElementById('pr-diff').textContent=r.diff||('+'+length+' m informal path; saves about '+saved+' seconds');
  document.getElementById('pr-evidence').textContent=r.evidence||(
    'Open aerial imagery shows a greenness drop of '+fmt(p.wear,1)+'σ with '+
    Math.round((p.continuity||0)*100)+'% corridor continuity.'
  );
  document.getElementById('pr-action').textContent=r.action||'Field-check before any OpenStreetMap edit. No automatic OSM writes.';
  document.getElementById('pr-wear').textContent='wear '+fmt(p.wear,2)+'σ';
  document.getElementById('pr-continuity').textContent='continuity '+Math.round((p.continuity||0)*100)+'%';
  document.getElementById('pr-model').textContent=r.source||p.model||'heuristic';
  document.getElementById('pr-score').textContent='score '+Math.round((p.score||0)*100)+'%';
}
function closePR(){document.getElementById('pull-request').hidden=true}
document.getElementById('close-pr').onclick=closePR;
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePR()});

Promise.all([
  fetch('data/desire-lines.geojson').then(r=>r.json()),
  fetch('data/metrics.json').then(r=>r.json())
]).then(([geo,metrics])=>{
  const bounds=[];
  let checks=0,longest=0;
  geo.features.forEach(f=>{
    const p=f.properties||{};
    const r=p.review||{};
    const v=r.verdict||'unclear';
    if(v!=='no') checks++;
    longest=Math.max(longest,p.seconds_saved||0);
    const layer=L.geoJSON(f,{style:{color:colors[v]||colors.unclear,weight:v==='yes'?6:4,opacity:.9,dashArray:v==='unclear'?'8 7':null}})
      .on('click',()=>openPR(f)).addTo(map);
    bounds.push(layer.getBounds());
  });
  document.getElementById('candidate-count').textContent=geo.features.length;
  document.getElementById('check-count').textContent=checks;
  document.getElementById('longest-shortcut').textContent=longest>=90?Math.round(longest/60)+' min':Math.round(longest)+' s';
  if(bounds.length){
    lineBounds=bounds.reduce((a,b)=>a.extend(b)).pad(.08);
    frameMap();
  }

  const primary=metrics.primary_model||'not ranked';
  document.getElementById('primary-model').textContent='Primary ranker on this run: '+primary+'.';
  const rows=[];
  const gate=metrics.tabpfn_import_error||(metrics.models&&metrics.models.tabpfn&&metrics.models.tabpfn.error);
  if(gate){
    rows.push('<div class="gate"><strong>TabPFN did not score</strong><p>Prior Labs blocked this run until the license is accepted and TABPFN_TOKEN is set. Logistic regression is the measured model.</p></div>');
  }
  rows.push(metricRow('Samples',metrics.samples||0,1));
  rows.push(metricRow('Mapped positives',metrics.positives||0,(metrics.positives||0)/Math.max(metrics.samples||1,1)));
  Object.entries(metrics.models||{}).forEach(([name,m])=>{
    if(m&&m.error){
      if(name==='tabpfn') return;
      rows.push('<div class="metric error"><span>'+name.replaceAll('_',' ')+'</span><strong>'+
        escapeHtml(String(m.error).split('\n')[0])+'</strong></div>');
      return;
    }
    if(m&&m.roc_auc!==undefined)rows.push(metricRow(name+' ROC-AUC',m.roc_auc,m.roc_auc));
    if(m&&m.pr_auc!==undefined)rows.push(metricRow(name+' PR-AUC',m.pr_auc,m.pr_auc));
  });
  document.getElementById('metrics').innerHTML=rows.join('');
}).catch(e=>{
  console.error(e);
  document.getElementById('candidate-count').textContent='0';
});
window.addEventListener('load',frameMap);
window.addEventListener('resize',()=>map.invalidateSize());

function metricRow(name,value,width){
  const label=String(name).replaceAll('_',' ');
  const shown=typeof value==='number'&&value<1&&value!==0?value.toFixed(3):value;
  return '<div class="metric"><span>'+label+'</span><strong>'+shown+
    '</strong><div class="bar"><i style="width:'+Math.min(100,(width||0)*100)+'%"></i></div></div>';
}
function escapeHtml(text){
  return text.replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
"""
