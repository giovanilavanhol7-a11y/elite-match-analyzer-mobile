const $ = (id) => document.getElementById(id);
const fixturesEl = $("fixtures");
const notice = $("notice");
const analysisPanel = $("analysisPanel");
let currentFixture = null;
let currentSample = 10;

function initials(name){return (name||"?").split(/\s+/).slice(0,2).map(x=>x[0]).join("").toUpperCase()}
function showNotice(text){ notice.textContent=text; notice.classList.toggle("hidden", !text); }

async function getJSON(url){
  const r = await fetch(url);
  const data = await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(data.error || data.message || "Erro ao carregar dados");
  return data;
}

function teamIcon(team){
  if(team.logo){
    return `<img class="mini-logo" src="${team.logo}" alt="">`;
  }
  return `<div class="mini-fallback">${initials(team.name)}</div>`;
}

function renderFixtures(items){
  if(!items.length){
    fixturesEl.innerHTML='<div class="card empty">Nenhuma partida encontrada para hoje.</div>';
    return;
  }
  fixturesEl.innerHTML = items.map(f=>`
    <button class="fixture" data-id="${f.id}">
      <div class="fixture-top">
        <span class="fixture-league">${f.league}</span>
        <span class="fixture-time">${f.time || f.status || "—"}</span>
      </div>
      <div class="fixture-teams">
        <div class="mini-team">${teamIcon(f.home)}<strong>${f.home.name}</strong></div>
        <span class="fixture-vs">x</span>
        <div class="mini-team"><strong>${f.away.name}</strong>${teamIcon(f.away)}</div>
      </div>
    </button>
  `).join("");
  document.querySelectorAll(".fixture").forEach(btn=>{
    btn.addEventListener("click",()=>{
      const item = items.find(x=>String(x.id)===btn.dataset.id);
      openAnalysis(item);
    });
  });
}

async function loadFixtures(){
  fixturesEl.innerHTML='<div class="card loader">Carregando jogos...</div>';
  try{
    const health=await getJSON("/api/health");
    $("modeBadge").textContent=health.api_configured && !health.demo_mode ? "DADOS REAIS" : "DEMO";
    $("modeBadge").style.color=health.api_configured && !health.demo_mode ? "var(--green)" : "var(--amber)";
    const data=await getJSON("/api/fixtures/today");
    showNotice(data.message || "");
    renderFixtures(data.fixtures || []);
    $("todayLabel").textContent = new Intl.DateTimeFormat("pt-BR",{dateStyle:"full"}).format(new Date());
  }catch(e){
    fixturesEl.innerHTML=`<div class="card empty error">${e.message}</div>`;
  }
}

function setBigTeam(prefix, team){
  $(`${prefix}Name`).textContent=team.name;
  const img=$(`${prefix}Logo`), fb=$(`${prefix}Fallback`);
  if(team.logo){
    img.src=team.logo; img.classList.remove("hidden"); fb.classList.add("hidden");
  }else{
    img.classList.add("hidden"); fb.classList.remove("hidden"); fb.textContent=initials(team.name);
  }
}

async function openAnalysis(fixture){
  currentFixture=fixture;
  fixturesEl.classList.add("hidden");
  document.querySelector(".intro").classList.add("hidden");
  showNotice("");
  analysisPanel.classList.remove("hidden");
  setBigTeam("home",fixture.home);
  setBigTeam("away",fixture.away);
  await loadAnalysis();
  window.scrollTo({top:0,behavior:"smooth"});
}

async function loadAnalysis(){
  $("statsList").innerHTML='<div class="loader">Calculando estatísticas...</div>';
  try{
    const data=await getJSON(`/api/analysis/${currentFixture.id}?sample=${currentSample}`);
    $("sourceLabel").textContent=data.source || "Fonte";
    $("sampleInfo").textContent=`${data.sample_size || currentSample} jogos usados`;
    $("statsList").innerHTML=(data.stats||[]).map(s=>`
      <div class="stat-row">
        <div class="stat-value">${Number(s.home).toFixed(2)}</div>
        <div class="stat-label">${s.label}</div>
        <div class="stat-value">${Number(s.away).toFixed(2)}</div>
      </div>
    `).join("") || '<div class="empty">Sem estatísticas disponíveis.</div>';
  }catch(e){
    $("statsList").innerHTML=`<div class="empty error">${e.message}</div>`;
  }
}

$("refreshBtn").addEventListener("click",loadFixtures);
$("backBtn").addEventListener("click",()=>{
  currentFixture=null;
  analysisPanel.classList.add("hidden");
  document.querySelector(".intro").classList.remove("hidden");
  fixturesEl.classList.remove("hidden");
});
document.querySelectorAll(".tab").forEach(btn=>{
  btn.addEventListener("click",async()=>{
    currentSample=Number(btn.dataset.sample);
    document.querySelectorAll(".tab").forEach(b=>b.classList.toggle("active",b===btn));
    if(currentFixture) await loadAnalysis();
  });
});
loadFixtures();
