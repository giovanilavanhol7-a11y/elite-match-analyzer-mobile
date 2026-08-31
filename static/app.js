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
const MIN_RECENT_GAMES = 4;


/* ======================================================
   PESO DA TENDÊNCIA
====================================================== */

const TREND_BONUS_UP = 0.3;
const TREND_BONUS_STABLE = 0;
const TREND_PENALTY_DOWN = -0.4;


/* ======================================================
   BÔNUS DE DIFICULDADE
====================================================== */

const LINE_DIFFICULTY_BONUS = {
  goals: {
    "0.5": 0
  },

  corners: {
    "3.5": 0,
    "4.5": 0.1
  },

  shots: {
    "9.5": 0,
    "12.5": 0.1
  },

  sot: {
    "2.5": 0,
    "3.5": 0.1
  },

  yellow_cards: {
    "0.5": 0,
    "1.5": 0.1,
    "2.5": 0.2
  },

  red_cards: {
    "0.5": 0
  },

  fouls: {
    "9.5": 0,
    "10.5": 0.1
  }
};


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
   CONTEXTO DA PARTIDA
====================================================== */

function renderMatchContext(data) {
  let contextCard =
    $("matchContextCard");

  const info =
    data.match_info || {};

  const referee =
    info.referee || "Não informado";

  const stadium =
    info.stadium || "Não informado";

  const round =
    info.round || "Não informada";

  const time =
    info.time ||
    currentFixture?.time ||
    "—";

  const status =
    info.status ||
    currentFixture?.status ||
    "—";

  if (!contextCard) {
    const statsCard =
      analysisPanel
        .querySelector(".card");

    if (!statsCard) {
      return;
    }

    contextCard =
      document.createElement("div");

    contextCard.id =
      "matchContextCard";

    contextCard.className =
      "card";

    contextCard.style.marginBottom =
      "16px";

    statsCard.insertAdjacentElement(
      "beforebegin",
      contextCard
    );
  }

  contextCard.innerHTML = `

    <div class="section-head">

      <h2>
        Contexto da partida
      </h2>

      <span>
        DADOS DA PITCHAPI
      </span>

    </div>

    <div
      style="
        display:grid;
        gap:10px;
        margin-top:12px;
      "
    >

      <div
        style="
          padding:12px;
          border-radius:11px;
          background:rgba(255,255,255,.04);
        "
      >

        <div
          style="
            font-size:11px;
            opacity:.65;
            margin-bottom:4px;
          "
        >
          👨‍⚖️ Árbitro
        </div>

        <strong>
          ${referee}
        </strong>

      </div>

      <div
        style="
          padding:12px;
          border-radius:11px;
          background:rgba(255,255,255,.04);
        "
      >

        <div
          style="
            font-size:11px;
            opacity:.65;
            margin-bottom:4px;
          "
        >
          🏟️ Estádio
        </div>

        <strong>
          ${stadium}
        </strong>

      </div>

      <div
        style="
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:8px;
        "
      >

        <div
          style="
            padding:11px;
            border-radius:10px;
            background:rgba(255,255,255,.04);
          "
        >

          <div
            style="
              font-size:11px;
              opacity:.65;
              margin-bottom:4px;
            "
          >
            Rodada
          </div>

          <strong>
            ${round}
          </strong>

        </div>

        <div
          style="
            padding:11px;
            border-radius:10px;
            background:rgba(255,255,255,.04);
          "
        >

          <div
            style="
              font-size:11px;
              opacity:.65;
              margin-bottom:4px;
            "
          >
            Horário
          </div>

          <strong>
            ${time}
          </strong>

        </div>

      </div>

      <div
        style="
          padding:10px 12px;
          border-radius:10px;
          background:rgba(255,255,255,.03);
          font-size:12px;
          opacity:.75;
        "
      >

        Status:
        <strong>
          ${status}
        </strong>

      </div>

    </div>

  `;
}


/* ======================================================
   H2H
====================================================== */

function renderH2H(data) {
  let h2hCard =
    $("h2hCard");

  const h2h =
    data.h2h || {};

  const homeName =
    data.home?.name ||
    currentFixture?.home?.name ||
    "Mandante";

  const awayName =
    data.away?.name ||
    currentFixture?.away?.name ||
    "Visitante";

  if (!h2hCard) {
    const statsCard =
      Array
        .from(
          analysisPanel.querySelectorAll(
            ".card"
          )
        )
        .find(
          card =>
            card.querySelector(
              "#statsList"
            )
        );

    if (!statsCard) {
      return;
    }

    h2hCard =
      document.createElement(
        "div"
      );

    h2hCard.id =
      "h2hCard";

    h2hCard.className =
      "card";

    h2hCard.style.marginBottom =
      "16px";

    statsCard.insertAdjacentElement(
      "beforebegin",
      h2hCard
    );
  }

  if (
    !h2h.available
  ) {
    h2hCard.innerHTML = `

      <div class="section-head">

        <h2>
          ⚔️ Confronto direto
        </h2>

        <span>
          H2H
        </span>

      </div>

      <div
        style="
          margin-top:12px;
          padding:13px;
          border-radius:11px;
          background:rgba(255,255,255,.04);
          font-size:13px;
          line-height:1.6;
          opacity:.75;
        "
      >

        Não foram encontrados dados
        suficientes de confronto direto
        para esta partida.

      </div>

    `;

    return;
  }

  const totalMatches =
    Number(
      h2h.total_matches || 0
    );

  const homeWins =
    Number(
      h2h.home_wins || 0
    );

  const draws =
    Number(
      h2h.draws || 0
    );

  const awayWins =
    Number(
      h2h.away_wins || 0
    );

  const recentMatches =
    Array.isArray(
      h2h.recent_matches
    )
      ? h2h.recent_matches
      : [];

  let recentHtml = "";

  if (!recentMatches.length) {
    recentHtml = `

      <div
        style="
          padding:12px;
          border-radius:10px;
          background:rgba(255,255,255,.035);
          font-size:12px;
          opacity:.7;
        "
      >

        Nenhum resultado recente
        disponível.

      </div>

    `;
  } else {
    recentHtml =
      recentMatches
        .map(match => {

          const matchHome =
            match.home?.name ||
            "Mandante";

          const matchAway =
            match.away?.name ||
            "Visitante";

          const scoreHome =
            match.score_home;

          const scoreAway =
            match.score_away;

          const date =
            match.date || "—";

          return `

            <div
              style="
                padding:11px 0;
                border-bottom:1px solid rgba(255,255,255,.07);
              "
            >

              <div
                style="
                  font-size:11px;
                  opacity:.6;
                  margin-bottom:6px;
                "
              >
                ${date}
              </div>

              <div
                style="
                  display:grid;
                  grid-template-columns:1fr auto 1fr;
                  align-items:center;
                  gap:8px;
                "
              >

                <div
                  style="
                    text-align:left;
                    font-size:12px;
                    font-weight:700;
                  "
                >
                  ${matchHome}
                </div>

                <div
                  style="
                    min-width:54px;
                    text-align:center;
                    padding:6px 8px;
                    border-radius:8px;
                    background:rgba(255,255,255,.06);
                    font-weight:800;
                  "
                >

                  ${scoreHome}
                  ×
                  ${scoreAway}

                </div>

                <div
                  style="
                    text-align:right;
                    font-size:12px;
                    font-weight:700;
                  "
                >
                  ${matchAway}
                </div>

              </div>

            </div>

          `;
        })
        .join("");
  }

  h2hCard.innerHTML = `

    <div class="section-head">

      <h2>
        ⚔️ Confronto direto
      </h2>

      <span>
        H2H
      </span>

    </div>

    <div
      style="
        margin-top:12px;
        padding:12px;
        border-radius:12px;
        background:rgba(255,255,255,.04);
      "
    >

      <div
        style="
          text-align:center;
          font-size:12px;
          opacity:.7;
          margin-bottom:12px;
        "
      >

        ${totalMatches}
        confrontos encontrados

      </div>

      <div
        style="
          display:grid;
          grid-template-columns:1fr 1fr 1fr;
          gap:8px;
        "
      >

        <div
          style="
            padding:11px 6px;
            border-radius:10px;
            background:rgba(255,255,255,.04);
            text-align:center;
          "
        >

          <div
            style="
              font-size:10px;
              opacity:.65;
              margin-bottom:5px;
            "
          >
            ${homeName}
          </div>

          <strong
            style="
              font-size:22px;
            "
          >
            ${homeWins}
          </strong>

          <div
            style="
              font-size:10px;
              opacity:.65;
              margin-top:3px;
            "
          >
            vitórias
          </div>

        </div>

        <div
          style="
            padding:11px 6px;
            border-radius:10px;
            background:rgba(255,255,255,.04);
            text-align:center;
          "
        >

          <div
            style="
              font-size:10px;
              opacity:.65;
              margin-bottom:5px;
            "
          >
            Empates
          </div>

          <strong
            style="
              font-size:22px;
            "
          >
            ${draws}
          </strong>

          <div
            style="
              font-size:10px;
              opacity:.65;
              margin-top:3px;
            "
          >
            jogos
          </div>

        </div>

        <div
          style="
            padding:11px 6px;
            border-radius:10px;
            background:rgba(255,255,255,.04);
            text-align:center;
          "
        >

          <div
            style="
              font-size:10px;
              opacity:.65;
              margin-bottom:5px;
            "
          >
            ${awayName}
          </div>

          <strong
            style="
              font-size:22px;
            "
          >
            ${awayWins}
          </strong>

          <div
            style="
              font-size:10px;
              opacity:.65;
              margin-top:3px;
            "
          >
            vitórias
          </div>

        </div>

      </div>

    </div>

    <div
      style="
        margin-top:16px;
        font-size:14px;
        font-weight:800;
        margin-bottom:8px;
      "
    >
      Últimos confrontos
    </div>

    <div
      style="
        padding:0 11px;
        border-radius:11px;
        background:rgba(255,255,255,.025);
      "
    >

      ${recentHtml}

    </div>

    <div
      style="
        margin-top:10px;
        font-size:11px;
        line-height:1.5;
        opacity:.6;
      "
    >

      O H2H é mostrado como contexto
      histórico. Ele ainda não altera
      automaticamente o ranking das
      oportunidades.

    </div>

  `;
}


/* ======================================================
   TEXTO DO HISTÓRICO DO ADVERSÁRIO
====================================================== */

function usesOpponentHistoryWording(metric) {
  return [
    "yellow_cards",
    "red_cards",
    "cards",
    "fouls"
  ].includes(metric);
}


function opponentLabel(
  item,
  opponent
) {
  if (
    usesOpponentHistoryWording(
      item.metric
    )
  ) {
    return `Adversários do ${opponent}`;
  }

  return `${opponent} concede`;
}


function opponentAverageLabel(item) {
  if (
    usesOpponentHistoryWording(
      item.metric
    )
  ) {
    return "Média dos adversários";
  }

  return "Média cedida";
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
   BÔNUS DA LINHA
====================================================== */

function difficultyAdjustment(
  metric,
  threshold
) {
  const metricTable =
    LINE_DIFFICULTY_BONUS[
      metric
    ];

  if (!metricTable) {
    return 0;
  }

  const key =
    Number(threshold)
      .toFixed(1);

  const bonus =
    metricTable[key];

  if (
    bonus === undefined ||
    bonus === null
  ) {
    return 0;
  }

  return Number(bonus);
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
    return "Índice muito forte";
  }

  if (score >= 8) {
    return "Índice forte";
  }

  if (score >= 7) {
    return "Índice moderado";
  }

  return "Índice fraco";
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
  trendName,
  metric,
  threshold
) {
  if (
    baseIndex === null ||
    baseIndex === undefined
  ) {
    return null;
  }

  const trendBonus =
    trendAdjustment(
      trendName
    );

  const difficultyBonus =
    difficultyAdjustment(
      metric,
      threshold
    );

  const result =
    clamp(
      Number(baseIndex) +
      trendBonus +
      difficultyBonus,
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
          background:rgba(255,255,255,.035);
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

  const difficultyBonus =
    item.difficultyBonus || 0;

  const difficultyText =
    difficultyBonus > 0
      ? `+${difficultyBonus.toFixed(1)}`
      : difficultyBonus.toFixed(1);

  const opponentText =
    usesOpponentHistoryWording(
      item.metric
    )
      ? "Histórico adversário"
      : "Adversário concede";

  return `

    <div
      style="
        margin-top:10px;
        padding:12px;
        border-radius:10px;
        background:rgba(255,255,255,.045);
      "
    >

      <div
        style="
          display:flex;
          justify-content:space-between;
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
          grid-template-columns:1fr 1fr;
          gap:8px;
        "
      >

        <div
          style="
            padding:9px;
            border-radius:9px;
            background:rgba(255,255,255,.035);
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
            background:rgba(255,255,255,.035);
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

        ${opponentText}:

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
          border-top:1px solid rgba(255,255,255,.07);
          display:flex;
          justify-content:space-between;
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
          justify-content:space-between;
          gap:10px;
          font-size:12px;
        "
      >

        <span
          style="
            opacity:.7;
          "
        >
          Ajuste da tendência
        </span>

        <strong>
          ${adjustmentText}
        </strong>

      </div>

      <div
        style="
          margin-top:7px;
          display:flex;
          justify-content:space-between;
          gap:10px;
          font-size:12px;
        "
      >

        <span
          style="
            opacity:.7;
          "
        >
          Bônus da linha
        </span>

        <strong>
          ${difficultyText}
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
      `histórico do adversário abaixo de ${MIN_CONCEDED_RATE}%`
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

      const threshold =
        lineThreshold(
          item.label
        );

      const temporary = {
        ...item,

        team:
          teamName,

        threshold:
          threshold
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

      const difficultyBonus =
        difficultyAdjustment(
          item.metric,
          threshold
        );

      const finalIndex =
        rankingIndex(
          baseIndex,
          trendName,
          item.metric,
          threshold
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

        difficultyBonus:
          difficultyBonus,

        index:
          finalIndex
      };

    });
}


/* ======================================================
   MAIOR LINHA APROVADA POR MÉTRICA
====================================================== */

function chooseHighestApprovedPerMetric(
  items
) {
  const groups = {};

  const approved =
    (items || []).filter(
      linePassesFilters
    );

  approved.forEach(
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

      if (
        candidate.threshold >
        current.threshold
      ) {

        groups[metric] =
          candidate;

        return;
      }

      if (
        candidate.threshold ===
          current.threshold &&
        (candidate.index ?? -1) >
        (current.index ?? -1)
      ) {

        groups[metric] =
          candidate;

        return;
      }

      if (
        candidate.threshold ===
          current.threshold &&
        (candidate.index ?? -1) ===
          (current.index ?? -1) &&
        Number(
          candidate.cross_rate || 0
        ) >
        Number(
          current.cross_rate || 0
        )
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
   MELHOR DESCARTADA POR MÉTRICA
====================================================== */

function chooseDiscardedPerMetric(
  items,
  approvedMetrics
) {
  const groups = {};

  const rejected =
    (items || []).filter(
      item =>
        !linePassesFilters(item)
    );

  rejected.forEach(
    candidate => {

      const metric =
        candidate.metric ||
        candidate.label;

      if (
        approvedMetrics.has(metric)
      ) {
        return;
      }

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
   CLASSIFICAR OPORTUNIDADES
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

  const homeApproved =
    chooseHighestApprovedPerMetric(
      homeItems
    );

  const awayApproved =
    chooseHighestApprovedPerMetric(
      awayItems
    );

  const approved =
    sortOpportunities([
      ...homeApproved,
      ...awayApproved
    ]);

  const homeApprovedMetrics =
    new Set(
      homeApproved.map(
        item => item.metric
      )
    );

  const awayApprovedMetrics =
    new Set(
      awayApproved.map(
        item => item.metric
      )
    );

  const homeDiscarded =
    chooseDiscardedPerMetric(
      homeItems,
      homeApprovedMetrics
    );

  const awayDiscarded =
    chooseDiscardedPerMetric(
      awayItems,
      awayApprovedMetrics
    );

  const discarded =
    sortOpportunities([
      ...homeDiscarded,
      ...awayDiscarded
    ]);

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
   FILTRO RECENTE DA SUGESTÃO PRINCIPAL
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
   CANDIDATOS DA SUGESTÃO PRINCIPAL
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

  const homeStrong =
    homeItems.filter(
      item =>
        linePassesFilters(item) &&
        passesRecentPrimaryFilter(
          item,
          data
        )
    );

  const awayStrong =
    awayItems.filter(
      item =>
        linePassesFilters(item) &&
        passesRecentPrimaryFilter(
          item,
          data
        )
    );

  const homeBest =
    chooseHighestApprovedPerMetric(
      homeStrong
    );

  const awayBest =
    chooseHighestApprovedPerMetric(
      awayStrong
    );

  return sortOpportunities([
    ...homeBest,
    ...awayBest
  ]);
}


/* ======================================================
   ESCOLHER SUGESTÃO PRINCIPAL
====================================================== */

function selectPrimarySuggestion(data) {
  const candidates =
    primaryCandidates(
      data
    );

  if (!candidates.length) {
    return null;
  }

  return candidates[0];
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
          border:1px solid rgba(255,255,255,.09);
          background:rgba(255,255,255,.035);
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

          Nenhuma linha passou ao mesmo
          tempo pelos filtros dos
          Últimos 10 e dos Últimos 5
          com força suficiente.

          <br><br>

          Nesse caso o sistema prefere
          não destacar uma sugestão
          principal.

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

  const opponentText =
    opponentLabel(
      item,
      opponent
    );

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

  const difficultyBonus =
    item.difficultyBonus || 0;

  const trendBonus =
    item.trendAdjustment || 0;

  const trendBonusText =
    trendBonus > 0
      ? `+${trendBonus.toFixed(1)}`
      : trendBonus.toFixed(1);

  const difficultyText =
    difficultyBonus > 0
      ? `+${difficultyBonus.toFixed(1)}`
      : difficultyBonus.toFixed(1);

  return `

    <div
      style="
        margin-bottom:24px;
        padding:16px;
        border-radius:16px;
        border:1px solid rgba(255,255,255,.12);
        background:rgba(255,255,255,.055);
      "
    >

      <div
        style="
          display:flex;
          justify-content:space-between;
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
            MAIOR LINHA APROVADA PELOS FILTROS
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
              color:${lineColor(
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
            índice ajustado
          </div>

        </div>

      </div>

      <div
        style="
          margin-top:18px;
          padding:14px;
          border-radius:12px;
          background:rgba(255,255,255,.05);
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
          grid-template-columns:1fr 1fr;
          gap:8px;
          margin-top:10px;
        "
      >

        <div
          style="
            padding:11px;
            border-radius:10px;
            background:rgba(255,255,255,.04);
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
            background:rgba(255,255,255,.04);
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
          background:rgba(255,255,255,.035);
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

        ${opponentText}:

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
          margin-top:10px;
          padding:11px;
          border-radius:10px;
          background:rgba(255,255,255,.035);
          font-size:12px;
          line-height:1.7;
        "
      >

        Índice base:
        <strong>
          ${item.baseIndex}/10
        </strong>

        <br>

        Tendência:
        <strong>
          ${trendBonusText}
        </strong>

        <br>

        Bônus da linha:
        <strong>
          ${difficultyText}
        </strong>

      </div>

      <div
        style="
          margin-top:12px;
          padding-top:12px;
          border-top:1px solid rgba(255,255,255,.08);
          font-size:12px;
          line-height:1.6;
          opacity:.75;
        "
      >

        Todas as linhas são testadas
        primeiro nos Últimos 10 e nos
        Últimos 5.

        Depois o sistema prioriza a
        maior linha da mesma métrica
        que continua aprovada pelos
        filtros.

        O bônus de dificuldade serve
        apenas para ordenar o ranking.

        Os dados são históricos e não
        garantem o resultado da partida.

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

  const opponentText =
    opponentLabel(
      item,
      opponent
    );

  const averageText =
    opponentAverageLabel(
      item
    );

  const produced =
    item.produced || {};

  const conceded =
    item.opponent_conceded || {};

  const difficultyBonus =
    item.difficultyBonus || 0;

  const difficultyText =
    difficultyBonus > 0
      ? `+${difficultyBonus.toFixed(1)}`
      : difficultyBonus.toFixed(1);

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
          justify-content:space-between;
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
              color:${lineColor(
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
              • tendência:
              ${
                item.trendAdjustment > 0
                  ? `+${item.trendAdjustment.toFixed(1)}`
                  : item.trendAdjustment.toFixed(1)
              }
              • bônus da linha:
              ${difficultyText}
              • final:
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
          background:rgba(255,255,255,.04);
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
          background:rgba(255,255,255,.04);
        "
      >

        <div
          style="
            font-size:12px;
            opacity:.7;
            margin-bottom:5px;
          "
        >

          ${opponentText}

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
                ${averageText}:
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
          border-top:1px solid rgba(255,255,255,.07);
          display:flex;
          justify-content:space-between;
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
            color:${lineColor(
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

  const opponentText =
    opponentLabel(
      item,
      opponent
    );

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
          justify-content:space-between;
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

        ${opponentText}:
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
          background:rgba(255,255,255,.035);
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

    const cards =
      analysisPanel
        .querySelectorAll(
          ".card"
        );

    const statsCard =
      Array.from(cards).find(
        card =>
          card.querySelector(
            "#statsList"
          )
      ) || cards[0];

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
          PRODUZ × HISTÓRICO ADVERSÁRIO
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
        histórico do adversário,
        tendência dos últimos 5
        contra os últimos 10 e aplica
        um pequeno bônus de dificuldade
        às linhas mais altas que já
        foram aprovadas.

      </p>

      <div
        id="bestOpportunities"
      ></div>

      <div
        style="
          margin-top:14px;
          padding:12px;
          border-radius:12px;
          background:rgba(255,255,255,.04);
          font-size:12px;
          line-height:1.5;
          opacity:.75;
        "
      >

        Para entrar nas oportunidades,
        a linha precisa atingir
        produção ≥ ${MIN_PRODUCED_RATE}%,
        histórico adversário ≥ ${MIN_CONCEDED_RATE}%
        e força combinada ≥ ${MIN_CROSS_RATE}%.

        A sugestão principal também
        precisa passar esses filtros
        nos Últimos 5, ter amostra
        recente suficiente e não pode
        estar enfraquecendo.

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

  html +=
    primarySuggestionCard(
      primary,
      data
    );

  html += `

    <div
      style="
        margin-bottom:20px;
      "
    >

      <div
        style="
          display:flex;
          justify-content:space-between;
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
          justify-content:space-between;
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

          Aqui aparecem métricas em
          que nenhuma das linhas
          disponíveis conseguiu passar
          pelos filtros principais.

          Bônus de linha ou tendência
          positiva nunca transformam
          uma linha reprovada em
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
                  border-bottom:1px solid rgba(255,255,255,.07);
                "
              >

                <div
                  style="
                    display:flex;
                    justify-content:space-between;
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
                border-bottom:1px solid rgba(255,255,255,.07);
              "
            >

              <div
                style="
                  display:flex;
                  justify-content:space-between;
                  gap:12px;
                  align-items:center;
                "
              >

                <span>
                  ${line.label}
                </span>

                <strong
                  style="
                    color:${lineColor(
                      line.rate
                    )};
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

            <div class="stat
