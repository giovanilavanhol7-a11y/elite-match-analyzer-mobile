const $ = (id) => document.getElementById(id);

const fixturesEl = $("fixtures");
const notice = $("notice");
const analysisPanel = $("analysisPanel");

let currentFixture = null;
let currentSample = 10;


/* ======================================================
   FILTROS PRINCIPAIS
====================================================== */

const MIN_PRODUCED_RATE = 75;
const MIN_CONCEDED_RATE = 75;
const MIN_CROSS_RATE = 80;

/*
  Para uma linha poder virar
  SUGESTÃO PRINCIPAL,
  exigimos pelo menos 4 jogos
  válidos no recorte recente.
*/

const MIN_RECENT_GAMES = 4;


/* ======================================================
   PESO DA TENDÊNCIA
====================================================== */

const TREND_BONUS_UP = 0.3;
const TREND_BONUS_STABLE = 0;
const TREND_PENALTY_DOWN = -0.4;


/* ======================================================
   AUXILIARES
====================================================== */

function initials(name) {
  return (name || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map(x => x[0])
    .join("")
    .toUpperCase();
}


function showNotice(text) {
  notice.textContent = text;

  notice.classList.toggle(
    "hidden",
    !text
  );
}


async function getJSON(url) {
  const response = await fetch(url);

  const data = await response
    .json()
    .catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.error ||
      data.message ||
      "Erro ao carregar dados"
    );
  }

  return data;
}


function formatStat(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "Sem dados";
  }

  const num = Number(value);

  if (Number.isNaN(num)) {
    return "Sem dados";
  }

  return num.toFixed(2);
}


function formatRate(value) {
  if (
    value === null ||
    value === undefined
  ) {
    return "Sem dados";
  }

  const num = Number(value);

  if (Number.isNaN(num)) {
    return "Sem dados";
  }

  return `${num.toFixed(1)}%`;
}


function clamp(value, min, max) {
  return Math.min(
    max,
    Math.max(min, value)
  );
}


/* ======================================================
   TIMES / ESCUDOS
====================================================== */

function teamIcon(team) {
  if (team.logo) {
    return `
      <img
        class="mini-logo"
        src="${team.logo}"
        alt=""
      >
    `;
  }

  return `
    <div class="mini-fallback">
      ${initials(team.name)}
    </div>
  `;
}


/* ======================================================
   PARTIDAS
====================================================== */

function renderFixtures(items) {
  if (!items.length) {
    fixturesEl.innerHTML = `
      <div class="card empty">
        Nenhuma partida encontrada para hoje.
      </div>
    `;

    return;
  }


  fixturesEl.innerHTML =
    items.map(f => `
      <button
        class="fixture"
        data-id="${f.id}"
      >

        <div class="fixture-top">

          <span class="fixture-league">
            ${f.league}
          </span>

          <span class="fixture-time">
            ${f.time || f.status || "—"}
          </span>

        </div>


        <div class="fixture-teams">

          <div class="mini-team">

            ${teamIcon(f.home)}

            <strong>
              ${f.home.name}
            </strong>

          </div>


          <span class="fixture-vs">
            x
          </span>


          <div class="mini-team">

            <strong>
              ${f.away.name}
            </strong>

            ${teamIcon(f.away)}

          </div>

        </div>

      </button>
    `).join("");


  document
    .querySelectorAll(".fixture")
    .forEach(btn => {

      btn.addEventListener(
        "click",
        () => {

          const item =
            items.find(
              x =>
                String(x.id) ===
                btn.dataset.id
            );

          if (item) {
            openAnalysis(item);
          }

        }
      );

    });
}


/* ======================================================
   CARREGAR PARTIDAS
====================================================== */

async function loadFixtures() {
  fixturesEl.innerHTML = `
    <div class="card loader">
      Carregando jogos...
    </div>
  `;


  try {

    const health =
      await getJSON(
        "/api/health"
      );


    $("modeBadge").textContent =
      health.api_configured &&
      !health.demo_mode
        ? "DADOS REAIS"
        : "DEMO";


    $("modeBadge").style.color =
      health.api_configured &&
      !health.demo_mode
        ? "var(--green)"
        : "var(--amber)";


    const data =
      await getJSON(
        "/api/fixtures/today"
      );


    showNotice(
      data.message || ""
    );


    renderFixtures(
      data.fixtures || []
    );


    $("todayLabel").textContent =
      new Intl.DateTimeFormat(
        "pt-BR",
        {
          dateStyle: "full"
        }
      ).format(
        new Date()
      );


  } catch (error) {

    fixturesEl.innerHTML = `
      <div class="card empty error">
        ${error.message}
      </div>
    `;

  }
}


/* ======================================================
   ABRIR ANÁLISE
====================================================== */

function setBigTeam(prefix, team) {
  $(`${prefix}Name`).textContent =
    team.name;


  const img =
    $(`${prefix}Logo`);


  const fallback =
    $(`${prefix}Fallback`);


  if (team.logo) {

    img.src = team.logo;

    img.classList.remove(
      "hidden"
    );

    fallback.classList.add(
      "hidden"
    );

  } else {

    img.classList.add(
      "hidden"
    );

    fallback.classList.remove(
      "hidden"
    );

    fallback.textContent =
      initials(team.name);

  }
}


async function openAnalysis(fixture) {
  currentFixture = fixture;


  fixturesEl.classList.add(
    "hidden"
  );


  const intro =
    document.querySelector(
      ".intro"
    );


  if (intro) {
    intro.classList.add(
      "hidden"
    );
  }


  showNotice("");


  analysisPanel.classList.remove(
    "hidden"
  );


  setBigTeam(
    "home",
    fixture.home
  );


  setBigTeam(
    "away",
    fixture.away
  );


  await loadAnalysis();


  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}


/* ======================================================
   CORES
====================================================== */

function lineColor(rate) {
  if (
    rate === null ||
    rate === undefined
  ) {
    return "var(--muted)";
  }


  if (rate >= 90) {
    return "var(--green)";
  }


  if (rate >= 80) {
    return "var(--amber)";
  }


  return "var(--muted)";
}


/* ======================================================
   VALOR DA LINHA
====================================================== */

function lineThreshold(label) {
  const match =
    String(label || "")
      .match(
        /\+?(\d+(?:[.,]\d+)?)/
      );


  if (!match) {
    return 0;
  }


  return Number(
    match[1].replace(
      ",",
      "."
    )
  );
}


/* ======================================================
   ÍNDICE HISTÓRICO BASE
====================================================== */

function crossIndex(item) {
  const producedRate =
    Number(
      item.produced?.rate
    );


  const concededRate =
    Number(
      item.opponent_conceded?.rate
    );


  if (
    Number.isNaN(producedRate) ||
    Number.isNaN(concededRate)
  ) {
    return null;
  }


  const averageRate =
    (
      producedRate +
      concededRate
    ) / 2;


  const weakerRate =
    Math.min(
      producedRate,
      concededRate
    );


  const producedGames =
    Number(
      item.produced?.games || 0
    );


  const concededGames =
    Number(
      item.opponent_conceded?.games || 0
    );


  const usableGames =
    Math.min(
      producedGames,
      concededGames
    );


  const sampleScore =
    clamp(
      usableGames / 10,
      0,
      1
    );


  const score =
    (
      (averageRate / 100) * 0.70 +
      (weakerRate / 100) * 0.20 +
      sampleScore * 0.10
    ) * 10;


  return Number(
    score.toFixed(1)
  );
}


/* ======================================================
   CLASSIFICAÇÃO
====================================================== */

function indexLabel(score) {
  if (score === null) {
    return "Sem dados";
  }


  if (score >= 9) {
    return "Histórico muito forte";
  }


  if (score >= 8) {
    return "Histórico forte";
  }


  if (score >= 7) {
    return "Histórico moderado";
  }


  return "Histórico fraco";
}


/* ======================================================
   TENDÊNCIA
====================================================== */

function trendInfo(trend) {
  if (trend === "subindo") {
    return {
      icon: "📈",
      label: "Subindo"
    };
  }


  if (trend === "enfraquecendo") {
    return {
      icon: "📉",
      label: "Enfraquecendo"
    };
  }


  if (trend === "mantida") {
    return {
      icon: "✅",
      label: "Mantida"
    };
  }


  return {
    icon: "➖",
    label: "Sem dados"
  };
}


/* ======================================================
   LOCALIZAR TENDÊNCIA
====================================================== */

function findTrend(
  item,
  data
) {
  const homeName =
    data.home?.name ||
    currentFixture.home.name;


  const side =
    item.team === homeName
      ? "home"
      : "away";


  const trends =
    data.trends?.[side] || [];


  return trends.find(
    trend =>
      trend.metric ===
        item.metric &&
      Number(trend.line) ===
        Number(item.line)
  ) || null;
}


/* ======================================================
   AJUSTE DA TENDÊNCIA
====================================================== */

function trendAdjustment(trendName) {
  if (trendName === "subindo") {
    return TREND_BONUS_UP;
  }


  if (trendName === "enfraquecendo") {
    return TREND_PENALTY_DOWN;
  }


  if (trendName === "mantida") {
    return TREND_BONUS_STABLE;
  }


  return 0;
}


/* ======================================================
   ÍNDICE FINAL
====================================================== */

function rankingIndex(
  baseIndex,
  trendName
) {
  if (
    baseIndex === null ||
    baseIndex === undefined
  ) {
    return null;
  }


  const adjustment =
    trendAdjustment(
      trendName
    );


  const result =
    clamp(
      Number(baseIndex) +
      adjustment,
      0,
      10
    );


  return Number(
    result.toFixed(1)
  );
}


/* ======================================================
   BLOCO DA TENDÊNCIA
====================================================== */

function trendBlock(
  item,
  data
) {
  const trend =
    findTrend(
      item,
      data
    );


  if (!trend) {

    return `
      <div
        style="
          margin-top:10px;
          padding:11px;
          border-radius:10px;
          background:
          rgba(255,255,255,.035);
          font-size:12px;
          opacity:.75;
        "
      >
        Tendência 5 × 10:
        sem dados suficientes.
      </div>
    `;
  }


  const recent5 =
    trend.recent_5 || {};


  const recent10 =
    trend.recent_10 || {};


  const produced5 =
    recent5.produced || {};


  const produced10 =
    recent10.produced || {};


  const conceded5 =
    recent5.opponent_conceded || {};


  const conceded10 =
    recent10.opponent_conceded || {};


  const info =
    trendInfo(
      trend.trend
    );


  const difference =
    trend.difference;


  let differenceText =
    "—";


  if (
    difference !== null &&
    difference !== undefined &&
    !Number.isNaN(
      Number(difference)
    )
  ) {

    const value =
      Number(difference);


    differenceText =
      value > 0
        ? `+${value.toFixed(1)} p.p.`
        : `${value.toFixed(1)} p.p.`;

  }


  const adjustment =
    trendAdjustment(
      trend.trend
    );


  let adjustmentText =
    adjustment.toFixed(1);


  if (adjustment > 0) {
    adjustmentText =
      `+${adjustment.toFixed(1)}`;
  }


  return `

    <div
      style="
        margin-top:10px;
        padding:12px;
        border-radius:10px;
        background:
        rgba(255,255,255,.045);
      "
    >

      <div
        style="
          display:flex;
          justify-content:
          space-between;
          align-items:center;
          gap:10px;
          margin-bottom:10px;
        "
      >

        <strong
          style="
            font-size:13px;
          "
        >
          Tendência 5 × 10
        </strong>


        <strong
          style="
            font-size:13px;
          "
        >
          ${info.icon}
          ${info.label}
        </strong>

      </div>


      <div
        style="
          display:grid;
          grid-template-columns:
          1fr 1fr;
          gap:8px;
        "
      >

        <div
          style="
            padding:9px;
            border-radius:9px;
            background:
            rgba(255,255,255,.035);
          "
        >

          <div
            style="
              font-size:11px;
              opacity:.65;
              margin-bottom:3px;
            "
          >
            Últimos 10
          </div>


          <strong>
            ${formatRate(
              recent10.cross_rate
            )}
          </strong>

        </div>


        <div
          style="
            padding:9px;
            border-radius:9px;
            background:
            rgba(255,255,255,.035);
          "
        >

          <div
            style="
              font-size:11px;
              opacity:.65;
              margin-bottom:3px;
            "
          >
            Últimos 5
          </div>


          <strong>
            ${formatRate(
              recent5.cross_rate
            )}
          </strong>

        </div>

      </div>


      <div
        style="
          margin-top:9px;
          font-size:12px;
          line-height:1.6;
          opacity:.78;
        "
      >

        Equipe produz:

        <strong>
          ${formatRate(
            produced10.rate
          )}
        </strong>
        nos 10

        →

        <strong>
          ${formatRate(
            produced5.rate
          )}
        </strong>
        nos 5

        <br>


        Adversário concede:

        <strong>
          ${formatRate(
            conceded10.rate
          )}
        </strong>
        nos 10

        →

        <strong>
          ${formatRate(
            conceded5.rate
          )}
        </strong>
        nos 5

      </div>


      <div
        style="
          margin-top:9px;
          padding-top:9px;
          border-top:
          1px solid
          rgba(255,255,255,.07);
          display:flex;
          justify-content:
          space-between;
          gap:10px;
          font-size:12px;
        "
      >

        <span
          style="
            opacity:.7;
          "
        >
          Variação
        </span>


        <strong>
          ${differenceText}
        </strong>

      </div>


      <div
        style="
          margin-top:7px;
          display:flex;
          justify-content:
          space-between;
          gap:10px;
          font-size:12px;
        "
      >

        <span
          style="
            opacity:.7;
          "
        >
          Ajuste no ranking
        </span>


        <strong>
          ${adjustmentText}
        </strong>

      </div>

    </div>

  `;
}


/* ======================================================
   FILTROS PRINCIPAIS
====================================================== */

function linePassesFilters(item) {
  const producedRate =
    Number(
      item.produced?.rate
    );


  const concededRate =
    Number(
      item.opponent_conceded?.rate
    );


  const crossRate =
    Number(
      item.cross_rate
    );


  if (
    Number.isNaN(producedRate) ||
    Number.isNaN(concededRate) ||
    Number.isNaN(crossRate)
  ) {
    return false;
  }


  return (
    producedRate >=
      MIN_PRODUCED_RATE &&

    concededRate >=
      MIN_CONCEDED_RATE &&

    crossRate >=
      MIN_CROSS_RATE
  );
}


/* ======================================================
   MOTIVOS DO DESCARTE
====================================================== */

function rejectionReasons(item) {
  const reasons = [];


  const producedRate =
    Number(
      item.produced?.rate
    );


  const concededRate =
    Number(
      item.opponent_conceded?.rate
    );


  const crossRate =
    Number(
      item.cross_rate
    );


  if (Number.isNaN(producedRate)) {

    reasons.push(
      "sem histórico suficiente de produção"
    );

  } else if (
    producedRate <
    MIN_PRODUCED_RATE
  ) {

    reasons.push(
      `produção abaixo de ${MIN_PRODUCED_RATE}%`
    );

  }


  if (Number.isNaN(concededRate)) {

    reasons.push(
      "sem histórico suficiente do adversário"
    );

  } else if (
    concededRate <
    MIN_CONCEDED_RATE
  ) {

    reasons.push(
      `adversário concede menos de ${MIN_CONCEDED_RATE}%`
    );

  }


  if (Number.isNaN(crossRate)) {

    reasons.push(
      "sem força combinada disponível"
    );

  } else if (
    crossRate <
    MIN_CROSS_RATE
  ) {

    reasons.push(
      `força combinada abaixo de ${MIN_CROSS_RATE}%`
    );

  }


  return reasons;
}


/* ======================================================
   PREPARAR LINHAS
====================================================== */

function prepareTeamLines(
  teamName,
  items,
  data
) {
  return (items || [])
    .map(item => {

      const temporary = {
        ...item,

        team:
          teamName,

        threshold:
          lineThreshold(
            item.label
          )
      };


      const baseIndex =
        crossIndex(
          temporary
        );


      const trend =
        findTrend(
          temporary,
          data
        );


      const trendName =
        trend?.trend ||
        "sem_dados";


      const finalIndex =
        rankingIndex(
          baseIndex,
          trendName
        );


      return {
        ...temporary,

        baseIndex:
          baseIndex,

        trendName:
          trendName,

        trendAdjustment:
          trendAdjustment(
            trendName
          ),

        index:
          finalIndex
      };

    });
}


/* ======================================================
   UMA LINHA POR MÉTRICA
====================================================== */

function chooseBestPerMetric(items) {
  const groups = {};


  (items || []).forEach(
    candidate => {

      const metric =
        candidate.metric ||
        candidate.label;


      const current =
        groups[metric];


      if (!current) {

        groups[metric] =
          candidate;

        return;
      }


      const candidateIndex =
        candidate.index ?? -1;


      const currentIndex =
        current.index ?? -1;


      if (
        candidateIndex >
        currentIndex
      ) {

        groups[metric] =
          candidate;

        return;
      }


      if (
        candidateIndex ===
          currentIndex &&
        Number(
          candidate.cross_rate || 0
        ) >
        Number(
          current.cross_rate || 0
        )
      ) {

        groups[metric] =
          candidate;

        return;
      }


      if (
        candidateIndex ===
          currentIndex &&
        Number(
          candidate.cross_rate || 0
        ) ===
        Number(
          current.cross_rate || 0
        ) &&
        candidate.threshold >
        current.threshold
      ) {

        groups[metric] =
          candidate;

      }

    }
  );


  return Object.values(
    groups
  );
}


/* ======================================================
   ORDENAR
====================================================== */

function sortOpportunities(items) {
  return [...items].sort(
    (a, b) => {

      const aIndex =
        a.index ?? -1;


      const bIndex =
        b.index ?? -1;


      if (
        bIndex !==
        aIndex
      ) {

        return (
          bIndex -
          aIndex
        );

      }


      const aCross =
        Number(
          a.cross_rate || 0
        );


      const bCross =
        Number(
          b.cross_rate || 0
        );


      if (
        bCross !==
        aCross
      ) {

        return (
          bCross -
          aCross
        );

      }


      return (
        b.threshold -
        a.threshold
      );

    }
  );
}


/* ======================================================
   CLASSIFICAR OPORTUNIDADES DA ABA
====================================================== */

function classifyOpportunities(data) {
  const homeName =
    data.home?.name ||
    currentFixture.home.name;


  const awayName =
    data.away?.name ||
    currentFixture.away.name;


  const homeItems =
    prepareTeamLines(
      homeName,
      data.cross?.home || [],
      data
    );


  const awayItems =
    prepareTeamLines(
      awayName,
      data.cross?.away || [],
      data
    );


  const homeBest =
    chooseBestPerMetric(
      homeItems
    );


  const awayBest =
    chooseBestPerMetric(
      awayItems
    );


  const allBest = [
    ...homeBest,
    ...awayBest
  ];


  const approved =
    sortOpportunities(
      allBest.filter(
        linePassesFilters
      )
    );


  const discarded =
    sortOpportunities(
      allBest.filter(
        item =>
          !linePassesFilters(item)
      )
    );


  return {
    approved:
      approved,

    top3:
      approved.slice(0, 3),

    good:
      approved.slice(3),

    discarded:
      discarded
  };
}


/* ======================================================
   CANDIDATOS DA SUGESTÃO PRINCIPAL

   A sugestão usa sempre o recorte
   de até 10 jogos como base,
   mesmo quando a pessoa toca
   na aba "Últimos 5".
====================================================== */

function primaryCandidates(data) {
  const homeName =
    data.home?.name ||
    currentFixture.home.name;


  const awayName =
    data.away?.name ||
    currentFixture.away.name;


  const homeCross =
    data.cross_samples
      ?.last_10
      ?.home ||
    data.cross?.home ||
    [];


  const awayCross =
    data.cross_samples
      ?.last_10
      ?.away ||
    data.cross?.away ||
    [];


  const homeItems =
    prepareTeamLines(
      homeName,
      homeCross,
      data
    );


  const awayItems =
    prepareTeamLines(
      awayName,
      awayCross,
      data
    );


  const homeBest =
    chooseBestPerMetric(
      homeItems
    );


  const awayBest =
    chooseBestPerMetric(
      awayItems
    );


  return sortOpportunities(
    [
      ...homeBest,
      ...awayBest
    ].filter(
      linePassesFilters
    )
  );
}


/* ======================================================
   FILTRO RECENTE DA SUGESTÃO PRINCIPAL

   Para virar sugestão principal:

   - passou nos 10
   - passou nos 5
   - pelo menos 4 jogos recentes válidos
   - não está enfraquecendo
====================================================== */

function passesRecentPrimaryFilter(
  item,
  data
) {
  const trend =
    findTrend(
      item,
      data
    );


  if (!trend) {
    return false;
  }


  if (
    trend.trend ===
    "enfraquecendo"
  ) {
    return false;
  }


  const recent5 =
    trend.recent_5 || {};


  const produced =
    recent5.produced || {};


  const conceded =
    recent5.opponent_conceded || {};


  const producedRate =
    Number(
      produced.rate
    );


  const concededRate =
    Number(
      conceded.rate
    );


  const crossRate =
    Number(
      recent5.cross_rate
    );


  const producedGames =
    Number(
      produced.games || 0
    );


  const concededGames =
    Number(
      conceded.games || 0
    );


  if (
    Number.isNaN(producedRate) ||
    Number.isNaN(concededRate) ||
    Number.isNaN(crossRate)
  ) {
    return false;
  }


  if (
    producedGames <
      MIN_RECENT_GAMES ||
    concededGames <
      MIN_RECENT_GAMES
  ) {
    return false;
  }


  return (
    producedRate >=
      MIN_PRODUCED_RATE &&

    concededRate >=
      MIN_CONCEDED_RATE &&

    crossRate >=
      MIN_CROSS_RATE
  );
}


/* ======================================================
   ESCOLHER UMA ÚNICA SUGESTÃO
====================================================== */

function selectPrimarySuggestion(data) {
  const candidates =
    primaryCandidates(
      data
    );


  const strongRecent =
    candidates.filter(
      item =>
        passesRecentPrimaryFilter(
          item,
          data
        )
    );


  if (!strongRecent.length) {
    return null;
  }


  return strongRecent[0];
}


/* ======================================================
   CARD DA SUGESTÃO PRINCIPAL
====================================================== */

function primarySuggestionCard(
  item,
  data
) {
  if (!item) {

    return `

      <div
        style="
          margin-bottom:22px;
          padding:15px;
          border-radius:14px;
          border:
          1px solid
          rgba(255,255,255,.09);
          background:
          rgba(255,255,255,.035);
        "
      >

        <div
          style="
            font-size:18px;
            font-weight:800;
            margin-bottom:8px;
          "
        >
          🎯 Sugestão principal
        </div>


        <div
          style="
            font-size:13px;
            line-height:1.6;
            opacity:.8;
          "
        >

          Nenhuma linha passou ao
          mesmo tempo pelos filtros
          dos Últimos 10 e dos
          Últimos 5 com força
          suficiente.

          <br><br>

          Nesse caso o sistema
          prefere não destacar uma
          sugestão principal.

        </div>

      </div>

    `;
  }


  const homeName =
    data.home?.name ||
    currentFixture.home.name;


  const awayName =
    data.away?.name ||
    currentFixture.away.name;


  const opponent =
    item.team === homeName
      ? awayName
      : homeName;


  const trend =
    findTrend(
      item,
      data
    ) || {};


  const recent5 =
    trend.recent_5 || {};


  const recent10 =
    trend.recent_10 || {};


  const produced10 =
    recent10.produced ||
    item.produced ||
    {};


  const conceded10 =
    recent10.opponent_conceded ||
    item.opponent_conceded ||
    {};


  const produced5 =
    recent5.produced || {};


  const conceded5 =
    recent5.opponent_conceded || {};


  const info =
    trendInfo(
      trend.trend
    );


  return `

    <div
      style="
        margin-bottom:24px;
        padding:16px;
        border-radius:16px;
        border:
        1px solid
        rgba(255,255,255,.12);
        background:
        rgba(255,255,255,.055);
      "
    >

      <div
        style="
          display:flex;
          justify-content:
          space-between;
          align-items:flex-start;
          gap:12px;
        "
      >

        <div>

          <div
            style="
              font-size:18px;
              font-weight:800;
              margin-bottom:5px;
            "
          >
            🎯 Sugestão principal
          </div>


          <div
            style="
              font-size:12px;
              opacity:.7;
            "
          >
            MELHOR CRUZAMENTO APROVADO
          </div>

        </div>


        <div
          style="
            text-align:right;
          "
        >

          <strong
            style="
              font-size:22px;
              color:
              ${lineColor(
                item.cross_rate
              )};
            "
          >

            ${item.index}/10

          </strong>


          <div
            style="
              font-size:11px;
              opacity:.7;
              margin-top:3px;
            "
          >

            índice histórico

          </div>

        </div>

      </div>


      <div
        style="
          margin-top:18px;
          padding:14px;
          border-radius:12px;
          background:
          rgba(255,255,255,.05);
        "
      >

        <div
          style="
            font-size:13px;
            opacity:.75;
            margin-bottom:5px;
          "
        >

          ${item.team}

        </div>


        <strong
          style="
            font-size:22px;
          "
        >

          ${item.label}

        </strong>


        <div
          style="
            margin-top:8px;
            font-size:13px;
          "
        >

          ${info.icon}
          <strong>
            ${info.label}
          </strong>

        </div>

      </div>


      <div
        style="
          display:grid;
          grid-template-columns:
          1fr 1fr;
          gap:8px;
          margin-top:10px;
        "
      >

        <div
          style="
            padding:11px;
            border-radius:10px;
            background:
            rgba(255,255,255,.04);
          "
        >

          <div
            style="
              font-size:11px;
              opacity:.65;
              margin-bottom:4px;
            "
          >
            Força últimos 10
          </div>


          <strong
            style="
              font-size:17px;
            "
          >

            ${formatRate(
              recent10.cross_rate ??
              item.cross_rate
            )}

          </strong>

        </div>


        <div
          style="
            padding:11px;
            border-radius:10px;
            background:
            rgba(255,255,255,.04);
          "
        >

          <div
            style="
              font-size:11px;
              opacity:.65;
              margin-bottom:4px;
            "
          >
            Força últimos 5
          </div>


          <strong
            style="
              font-size:17px;
            "
          >

            ${formatRate(
              recent5.cross_rate
            )}

          </strong>

        </div>

      </div>


      <div
        style="
          margin-top:10px;
          padding:12px;
          border-radius:10px;
          background:
          rgba(255,255,255,.035);
          font-size:12px;
          line-height:1.7;
        "
      >

        ${item.team} produz:

        <strong>
          ${formatRate(
            produced10.rate
          )}
        </strong>
        nos 10

        →

        <strong>
          ${formatRate(
            produced5.rate
          )}
        </strong>
        nos 5

        <br>


        ${opponent} concede:

        <strong>
          ${formatRate(
            conceded10.rate
          )}
        </strong>
        nos 10

        →

        <strong>
          ${formatRate(
            conceded5.rate
          )}
        </strong>
        nos 5

      </div>


      <div
        style="
          margin-top:12px;
          padding-top:12px;
          border-top:
          1px solid
          rgba(255,255,255,.08);
          font-size:12px;
          line-height:1.6;
          opacity:.75;
        "
      >

        Esta é a linha que melhor
        passou pelos filtros históricos
        e recentes do sistema.

        É uma sugestão baseada em dados
        passados, não uma garantia de
        resultado.

      </div>

    </div>

  `;
}


/* ======================================================
   CARD DA OPORTUNIDADE
====================================================== */

function opportunityCard(
  item,
  data,
  rank = null
) {
  const homeName =
    data.home?.name ||
    currentFixture.home.name;


  const awayName =
    data.away?.name ||
    currentFixture.away.name;


  const opponent =
    item.team === homeName
      ? awayName
      : homeName;


  const produced =
    item.produced || {};


  const conceded =
    item.opponent_conceded || {};


  return `

    <div
      class="safe-box"
      style="
        margin-bottom:14px;
      "
    >

      <div
        style="
          display:flex;
          justify-content:
          space-between;
          align-items:flex-start;
          gap:12px;
        "
      >

        <div>

          <div
            style="
              font-size:12px;
              opacity:.7;
              margin-bottom:4px;
            "
          >

            ${
              rank !== null
                ? `${rank}. `
                : ""
            }

            ${item.team}

          </div>


          <strong
            style="
              font-size:16px;
            "
          >

            ${item.label}

          </strong>

        </div>


        <div
          style="
            text-align:right;
          "
        >

          <strong
            style="
              font-size:20px;
              color:
              ${lineColor(
                item.cross_rate
              )};
            "
          >

            ${
              item.index !== null
                ? `${item.index}/10`
                : "—"
            }

          </strong>


          <small
            style="
              display:block;
              opacity:.75;
              margin-top:3px;
            "
          >

            ${indexLabel(
              item.index
            )}

          </small>

        </div>

      </div>


      ${
        item.baseIndex !== null &&
        item.baseIndex !== undefined
          ? `
            <div
              style="
                margin-top:8px;
                font-size:11px;
                opacity:.65;
              "
            >
              Índice base:
              ${item.baseIndex}/10
              • ranking com tendência:
              ${item.index}/10
            </div>
          `
          : ""
      }


      <div
        style="
          margin-top:14px;
          padding:11px;
          border-radius:10px;
          background:
          rgba(255,255,255,.04);
        "
      >

        <div
          style="
            font-size:12px;
            opacity:.7;
            margin-bottom:5px;
          "
        >

          ${item.team} produz

        </div>


        <strong>
          ${formatRate(
            produced.rate
          )}
        </strong>


        <span
          style="
            opacity:.75;
            margin-left:5px;
          "
        >

          • ${produced.hits || 0}
          de ${produced.games || 0}
          jogos

        </span>


        ${
          produced.average !==
          null &&
          produced.average !==
          undefined

            ? `
              <div
                style="
                  margin-top:5px;
                  font-size:12px;
                  opacity:.75;
                "
              >
                Média:
                ${Number(
                  produced.average
                ).toFixed(2)}
              </div>
            `

            : ""
        }

      </div>


      <div
        style="
          margin-top:8px;
          padding:11px;
          border-radius:10px;
          background:
          rgba(255,255,255,.04);
        "
      >

        <div
          style="
            font-size:12px;
            opacity:.7;
            margin-bottom:5px;
          "
        >

          ${opponent} concede

        </div>


        <strong>
          ${formatRate(
            conceded.rate
          )}
        </strong>


        <span
          style="
            opacity:.75;
            margin-left:5px;
          "
        >

          • ${conceded.hits || 0}
          de ${conceded.games || 0}
          jogos

        </span>


        ${
          conceded.average !==
          null &&
          conceded.average !==
          undefined

            ? `
              <div
                style="
                  margin-top:5px;
                  font-size:12px;
                  opacity:.75;
                "
              >
                Média cedida:
                ${Number(
                  conceded.average
                ).toFixed(2)}
              </div>
            `

            : ""
        }

      </div>


      <div
        style="
          margin-top:10px;
          padding-top:10px;
          border-top:
          1px solid
          rgba(255,255,255,.07);
          display:flex;
          justify-content:
          space-between;
          align-items:center;
          gap:10px;
        "
      >

        <small
          style="
            opacity:.75;
          "
        >
          Força combinada
        </small>


        <strong
          style="
            color:
            ${lineColor(
              item.cross_rate
            )};
          "
        >

          ${formatRate(
            item.cross_rate
          )}

        </strong>

      </div>


      ${trendBlock(
        item,
        data
      )}

    </div>

  `;
}


/* ======================================================
   CARD DESCARTADO
====================================================== */

function discardedCard(
  item,
  data
) {
  const homeName =
    data.home?.name ||
    currentFixture.home.name;


  const awayName =
    data.away?.name ||
    currentFixture.away.name;


  const opponent =
    item.team === homeName
      ? awayName
      : homeName;


  const produced =
    item.produced || {};


  const conceded =
    item.opponent_conceded || {};


  const reasons =
    rejectionReasons(item);


  return `

    <div
      class="safe-box"
      style="
        margin-bottom:10px;
        opacity:.82;
      "
    >

      <div
        style="
          display:flex;
          justify-content:
          space-between;
          gap:12px;
          align-items:flex-start;
        "
      >

        <div>

          <div
            style="
              font-size:12px;
              opacity:.7;
              margin-bottom:4px;
            "
          >
            ${item.team}
          </div>


          <strong>
            ${item.label}
          </strong>

        </div>


        <strong
          style="
            font-size:14px;
            opacity:.75;
          "
        >

          ${
            item.index !== null
              ? `${item.index}/10`
              : "—"
          }

        </strong>

      </div>


      <div
        style="
          margin-top:10px;
          font-size:12px;
          line-height:1.6;
          opacity:.8;
        "
      >

        ${item.team}:
        <strong>
          ${formatRate(
            produced.rate
          )}
        </strong>

        <br>

        ${opponent} concede:
        <strong>
          ${formatRate(
            conceded.rate
          )}
        </strong>

        <br>

        Força:
        <strong>
          ${formatRate(
            item.cross_rate
          )}
        </strong>

      </div>


      <div
        style="
          margin-top:10px;
          padding:9px 10px;
          border-radius:9px;
          background:
          rgba(255,255,255,.035);
          font-size:12px;
          line-height:1.5;
        "
      >

        🚫
        ${reasons.join(" • ")}

      </div>


      ${trendBlock(
        item,
        data
      )}

    </div>

  `;
}


/* ======================================================
   TOP 3 / BOAS / DESCARTADAS
====================================================== */

function renderBestOpportunities(data) {
  let container =
    $("bestOpportunities");


  if (!container) {

    const statsCard =
      analysisPanel
        .querySelectorAll(
          ".card"
        )[1];


    if (!statsCard) {
      return;
    }


    const box =
      document.createElement(
        "div"
      );


    box.className =
      "card";


    box.id =
      "bestOpportunitiesCard";


    box.style.marginTop =
      "16px";


    box.innerHTML = `

      <div class="section-head">

        <h2>
          Análise cruzada
        </h2>

        <span>
          PRODUZ × CEDE
        </span>

      </div>


      <p
        class="muted"
        style="
          margin-top:0;
          margin-bottom:16px;
        "
      >

        O sistema cruza produção,
        histórico do adversário e
        tendência dos últimos 5
        contra os últimos 10.

      </p>


      <div
        id="bestOpportunities"
      ></div>


      <div
        style="
          margin-top:14px;
          padding:12px;
          border-radius:12px;
          background:
          rgba(255,255,255,.04);
          font-size:12px;
          line-height:1.5;
          opacity:.75;
        "
      >

        Para entrar nas oportunidades,
        a linha precisa atingir
        produção ≥ ${MIN_PRODUCED_RATE}%,
        adversário ≥ ${MIN_CONCEDED_RATE}%
        e força combinada ≥ ${MIN_CROSS_RATE}%.

        A sugestão principal é ainda
        mais rígida: também precisa
        passar esses filtros nos
        Últimos 5 e não pode estar
        enfraquecendo.

        Os indicadores são históricos
        e não representam garantia
        de resultado.

      </div>

    `;


    statsCard.insertAdjacentElement(
      "afterend",
      box
    );


    container =
      $("bestOpportunities");
  }


  const result =
    classifyOpportunities(
      data
    );


  const primary =
    selectPrimarySuggestion(
      data
    );


  let html = "";


  /* ====================================================
     SUGESTÃO PRINCIPAL
  ==================================================== */

  html +=
    primarySuggestionCard(
      primary,
      data
    );


  /* ====================================================
     TOP 3
  ==================================================== */

  html += `

    <div
      style="
        margin-bottom:20px;
      "
    >

      <div
        style="
          display:flex;
          justify-content:
          space-between;
          align-items:center;
          gap:10px;
          margin-bottom:12px;
        "
      >

        <strong
          style="
            font-size:17px;
          "
        >
          🥇 Top 3
        </strong>


        <span
          style="
            font-size:11px;
            opacity:.7;
          "
        >
          RANKING ATUAL
        </span>

      </div>

  `;


  if (!result.top3.length) {

    html += `

      <div class="safe-box">

        Nenhuma linha atingiu
        os filtros mínimos.

      </div>

    `;

  } else {

    html +=
      result.top3
        .map(
          (item, index) =>
            opportunityCard(
              item,
              data,
              index + 1
            )
        )
        .join("");

  }


  html += `
    </div>
  `;


  /* ====================================================
     BOAS OPORTUNIDADES
  ==================================================== */

  html += `

    <div
      style="
        margin-top:22px;
        margin-bottom:20px;
      "
    >

      <div
        style="
          display:flex;
          justify-content:
          space-between;
          align-items:center;
          gap:10px;
          margin-bottom:12px;
        "
      >

        <strong
          style="
            font-size:17px;
          "
        >
          ✅ Boas oportunidades
        </strong>


        <span
          style="
            font-size:11px;
            opacity:.7;
          "
        >
          APROVADAS
        </span>

      </div>

  `;


  if (!result.good.length) {

    html += `

      <div
        class="safe-box"
        style="
          font-size:13px;
          opacity:.8;
        "
      >

        Nenhuma outra linha passou
        pelos filtros.

      </div>

    `;

  } else {

    html +=
      result.good
        .map(
          item =>
            opportunityCard(
              item,
              data
            )
        )
        .join("");

  }


  html += `
    </div>
  `;


  /* ====================================================
     DESCARTADAS
  ==================================================== */

  html += `

    <details
      style="
        margin-top:22px;
      "
    >

      <summary
        style="
          cursor:pointer;
          font-weight:700;
          font-size:16px;
          padding:10px 0;
        "
      >

        🚫 Descartadas
        (${result.discarded.length})

      </summary>


      <div
        style="
          margin-top:12px;
        "
      >

        <p
          style="
            font-size:12px;
            opacity:.7;
            line-height:1.5;
            margin-top:0;
          "
        >

          Não passaram em pelo menos
          um dos filtros principais.

          Uma tendência positiva não
          transforma automaticamente
          uma linha descartada em
          oportunidade aprovada.

        </p>

  `;


  if (!result.discarded.length) {

    html += `

      <div class="safe-box">

        Nenhuma linha descartada.

      </div>

    `;

  } else {

    html +=
      result.discarded
        .map(
          item =>
            discardedCard(
              item,
              data
            )
        )
        .join("");

  }


  html += `

      </div>

    </details>

  `;


  container.innerHTML =
    html;
}


/* ======================================================
   HISTÓRICO INDIVIDUAL
====================================================== */

function renderTeamLines(
  teamName,
  lines
) {
  if (
    !lines ||
    !lines.length
  ) {

    return `

      <div class="safe-box">

        <strong>
          ${teamName}
        </strong>

        <p>
          Sem dados suficientes.
        </p>

      </div>

    `;

  }


  return `

    <div
      class="safe-box"
      style="
        margin-bottom:14px
      "
    >

      <strong>
        ${teamName}
      </strong>


      <div
        style="
          display:grid;
          gap:10px;
          margin-top:12px;
        "
      >

        ${lines.map(line => {

          if (
            line.rate === null ||
            !line.games
          ) {

            return `

              <div
                style="
                  padding:10px 0;
                  border-bottom:
                  1px solid
                  rgba(255,255,255,.07);
                "
              >

                <div
                  style="
                    display:flex;
                    justify-content:
                    space-between;
                    gap:12px;
                  "
                >

                  <span>
                    ${line.label}
                  </span>

                  <strong>
                    Sem dados
                  </strong>

                </div>

              </div>

            `;

          }


          return `

            <div
              style="
                padding:10px 0;
                border-bottom:
                1px solid
                rgba(255,255,255,.07);
              "
            >

              <div
                style="
                  display:flex;
                  justify-content:
                  space-between;
                  gap:12px;
                  align-items:center;
                "
              >

                <span>
                  ${line.label}
                </span>


                <strong
                  style="
                    color:
                    ${lineColor(
                      line.rate
                    )}
                  "
                >

                  ${line.rate}%

                </strong>

              </div>


              <small
                style="
                  display:block;
                  margin-top:4px;
                  opacity:.75;
                "
              >

                Bateu ${line.hits}
                de ${line.games} jogos

              </small>

            </div>

          `;

        }).join("")}

      </div>

    </div>

  `;
}


/* ======================================================
   HISTÓRICO DAS LINHAS
====================================================== */

function renderLines(data) {
  let linesContainer =
    $("linesResults");


  const homeUsed =
    data.home?.matches_used ??
    currentSample;


  const awayUsed =
    data.away?.matches_used ??
    currentSample;


  if (!linesContainer) {

    const cards =
      analysisPanel
        .querySelectorAll(
          ".card"
        );


    const automaticSection =
      cards[cards.length - 1];


    if (!automaticSection) {
      return;
    }


    automaticSection.innerHTML = `

      <div class="section-head">

        <h2>
          Histórico das linhas
        </h2>

        <span
          id="linesSampleInfo"
        >

          ${homeUsed} casa •
          ${awayUsed} fora

        </span>

      </div>


      <p
        class="muted"
        style="
          margin-top:0;
          margin-bottom:16px;
        "
      >

        Histórico individual de
        cada equipe no recorte
        casa/fora.

      </p>


      <div
        id="linesResults"
      ></div>

    `;


    linesContainer =
      $("linesResults");

  } else {

    const sampleInfo =
      $("linesSampleInfo");


    if (sampleInfo) {

      sampleInfo.textContent =
        `${homeUsed} casa • ${awayUsed} fora`;

    }

  }


  const homeLines =
    data.lines?.home || [];


  const awayLines =
    data.lines?.away || [];


  linesContainer.innerHTML = `

    ${renderTeamLines(
      data.home?.name ||
      currentFixture.home.name,
      homeLines
    )}


    ${renderTeamLines(
      data.away?.name ||
      currentFixture.away.name,
      awayLines
    )}

  `;
}


/* ======================================================
   CARREGAR ANÁLISE
====================================================== */

async function loadAnalysis() {

  $("statsList").innerHTML = `

    <div class="loader">
      Calculando estatísticas...
    </div>

  `;


  try {

    const data =
      await getJSON(
        `/api/analysis/${currentFixture.id}?sample=${currentSample}`
      );


    $("sourceLabel").textContent =
      data.source || "Fonte";


    const homeUsed =
      data.home?.matches_used;


    const awayUsed =
      data.away?.matches_used;


    if (
      homeUsed !== undefined &&
      awayUsed !== undefined
    ) {

      $("sampleInfo").textContent =
        `${homeUsed} casa • ${awayUsed} fora`;

    } else {

      $("sampleInfo").textContent =
        `${data.sample_size || currentSample} jogos usados`;

    }


    $("statsList").innerHTML =
      (data.stats || [])
        .map(s => `

          <div class="stat-row">

            <div class="stat-value">
              ${formatStat(
                s.home
              )}
            </div>


            <div class="stat-label">
              ${s.label}
            </div>


            <div class="stat-value">
              ${formatStat(
                s.away
              )}
            </div>

          </div>

        `)
        .join("") ||

      `

        <div class="empty">
          Sem estatísticas disponíveis.
        </div>

      `;


    renderBestOpportunities(
      data
    );


    renderLines(
      data
    );


  } catch (error) {

    $("statsList").innerHTML = `

      <div class="empty error">
        ${error.message}
      </div>

    `;

  }
}


/* ======================================================
   ATUALIZAR
====================================================== */

$("refreshBtn")
  .addEventListener(
    "click",
    loadFixtures
  );


/* ======================================================
   VOLTAR
====================================================== */

$("backBtn")
  .addEventListener(
    "click",
    () => {

      currentFixture = null;


      analysisPanel.classList.add(
        "hidden"
      );


      const intro =
        document.querySelector(
          ".intro"
        );


      if (intro) {
        intro.classList.remove(
          "hidden"
        );
      }


      fixturesEl.classList.remove(
        "hidden"
      );

    }
  );


/* ======================================================
   ÚLTIMOS 5 / 10
====================================================== */

document
  .querySelectorAll(".tab")
  .forEach(btn => {

    btn.addEventListener(
      "click",
      async () => {

        currentSample =
          Number(
            btn.dataset.sample
          );


        document
          .querySelectorAll(".tab")
          .forEach(b => {

            b.classList.toggle(
              "active",
              b === btn
            );

          });


        if (currentFixture) {
          await loadAnalysis();
        }

      }
    );

  });


/* ======================================================
   INICIAR
====================================================== */

loadFixtures();
