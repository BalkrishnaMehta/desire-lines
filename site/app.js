const tabs=[...document.querySelectorAll('.nav')];
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
