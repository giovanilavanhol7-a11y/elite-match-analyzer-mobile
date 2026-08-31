const $ = (id) => document.getElementById(id);

const fixturesEl = $("fixtures");
const notice = $("notice");
const analysisPanel = $("analysisPanel");

let currentFixture = null;
let currentSample = 10;


/* ======================================================
   CONFIGURAÇÃO DOS FILTROS
====================================================== */

const MIN_PRODUCED_RATE = 75;
const MIN_CONCEDED_RATE = 75;
const MIN_CROSS_RATE = 80;


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
   JOGOS DO DIA
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
   PEGAR VALOR DA LINHA
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
   ÍNDICE HISTÓRICO COMBINADO

   70% = média das duas tendências
   20% = lado mais fraco
   10% = quantidade de jogos

   NÃO É PROBABILIDADE DE ACERTO.
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
   VERIFICAR SE A LINHA PASSOU NOS FILTROS
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
   MOTIVO DA LINHA SER DESCARTADA
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
   PREPARAR LINHAS DE UM TIME
====================================================== */

function prepareTeamLines(
  teamName,
  items
) {
  return (items || [])
    .map(item => ({
      ...item,

      team:
        teamName,

      threshold:
        lineThreshold(
          item.label
        ),

      index:
        crossIndex(item)
    }));
}


/* ======================================================
   ESCOLHER SÓ UMA LINHA POR MÉTRICA

   IMPORTANTE:
   Aqui ainda entram aprovadas e descartadas.

   Assim podemos mostrar ao usuário
   por que determinada estatística
   não passou no filtro.
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


      /*
        Primeiro:
        maior índice histórico.
      */

      if (
        candidateIndex >
        currentIndex
      ) {

        groups[metric] =
          candidate;

        return;
      }


      /*
        Segundo:
        maior força combinada.
      */

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


      /*
        Terceiro:
        linha mais alta.
      */

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
   ORDENAR POR FORÇA
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
   CLASSIFICAR TODAS AS OPORTUNIDADES
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
      data.cross?.home || []
    );


  const awayItems =
    prepareTeamLines(
      awayName,
      data.cross?.away || []
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
    top3:
      approved.slice(0, 3),

    good:
      approved.slice(3),

    discarded:
      discarded
  };
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

    </div>

  `;
}


/* ======================================================
   RENDERIZAR TOP 3 / BOAS / DESCARTADAS
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

        O sistema cruza o desempenho
        da equipe com o que o adversário
        costuma conceder.

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

        O Índice Histórico Combinado
        é uma classificação baseada
        no histórico recente.

        Ele não representa probabilidade
        garantida de acerto.

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


  let html = "";


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
          MAIS FORTES
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
          um dos filtros:
          produção ≥ ${MIN_PRODUCED_RATE}%,
          adversário concede ≥ ${MIN_CONCEDED_RATE}%
          e força combinada ≥ ${MIN_CROSS_RATE}%.

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
                  rgba(
                    255,
                    255,
                    255,
                    .07
                  );
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
                rgba(
                  255,
                  255,
                  255,
                  .07
                );
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
   RENDERIZAR HISTÓRICO
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
          Sem estatísticas
          disponíveis.
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
