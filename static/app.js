const $ = (id) => document.getElementById(id);

const fixturesEl = $("fixtures");
const notice = $("notice");
const analysisPanel = $("analysisPanel");

let currentFixture = null;
let currentSample = 10;


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
  notice.classList.toggle("hidden", !text);
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

  fixturesEl.innerHTML = items.map(f => `
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
          <strong>${f.home.name}</strong>
        </div>

        <span class="fixture-vs">
          x
        </span>

        <div class="mini-team">
          <strong>${f.away.name}</strong>
          ${teamIcon(f.away)}
        </div>

      </div>
    </button>
  `).join("");

  document
    .querySelectorAll(".fixture")
    .forEach(btn => {

      btn.addEventListener("click", () => {

        const item = items.find(
          x =>
            String(x.id) ===
            btn.dataset.id
        );

        openAnalysis(item);
      });

    });
}


async function loadFixtures() {
  fixturesEl.innerHTML = `
    <div class="card loader">
      Carregando jogos...
    </div>
  `;

  try {

    const health = await getJSON(
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

    const data = await getJSON(
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

  document
    .querySelector(".intro")
    .classList.add("hidden");

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
   CORES / FORÇA
====================================================== */

function lineColor(rate) {
  if (rate === null) {
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


function strengthLabel(rate) {
  if (rate >= 90) {
    return "Muito forte";
  }

  if (rate >= 80) {
    return "Forte";
  }

  return "";
}


/* ======================================================
   IDENTIFICAR TIPO DA ESTATÍSTICA
====================================================== */

function metricKey(label) {
  const text = String(label || "")
    .toLowerCase();

  if (text.includes("gol")) {
    return "goals";
  }

  if (text.includes("escanteio")) {
    return "corners";
  }

  if (text.includes("finaliza")) {
    return "shots";
  }

  if (
    text.includes("chutes no gol") ||
    text.includes("chute no gol")
  ) {
    return "sot";
  }

  if (text.includes("cart")) {
    return "cards";
  }

  if (text.includes("falta")) {
    return "fouls";
  }

  return text;
}


/* ======================================================
   PEGAR VALOR DA LINHA
   Exemplo:
   +3.5 Chutes no gol -> 3.5
====================================================== */

function lineThreshold(label) {
  const match = String(label || "")
    .match(/\+?(\d+(?:[.,]\d+)?)/);

  if (!match) {
    return 0;
  }

  return Number(
    match[1].replace(",", ".")
  );
}


/* ======================================================
   ESCOLHER MELHOR LINHA DE CADA MÉTRICA

   Regras:
   1 - precisa ter 80% ou mais
   2 - maior porcentagem vence
   3 - se porcentagem empatar,
       linha mais alta vence
====================================================== */

function chooseBestTeamLines(
  teamName,
  lines
) {
  const groups = {};

  (lines || []).forEach(line => {

    if (
      line.rate === null ||
      !line.games ||
      line.rate < 80
    ) {
      return;
    }

    const metric =
      metricKey(line.label);

    const candidate = {
      team: teamName,
      metric: metric,
      label: line.label,
      threshold:
        lineThreshold(line.label),
      rate: Number(line.rate),
      hits: Number(line.hits),
      games: Number(line.games)
    };

    const current =
      groups[metric];

    if (!current) {
      groups[metric] = candidate;
      return;
    }

    /*
      Maior taxa histórica
    */
    if (
      candidate.rate >
      current.rate
    ) {
      groups[metric] = candidate;
      return;
    }

    /*
      Se a taxa for igual,
      usa a linha mais alta.
    */
    if (
      candidate.rate ===
        current.rate &&
      candidate.threshold >
        current.threshold
    ) {
      groups[metric] = candidate;
    }

  });

  return Object.values(groups);
}


/* ======================================================
   MELHORES OPORTUNIDADES
====================================================== */

function getBestOpportunities(data) {
  const homeName =
    data.home?.name ||
    currentFixture.home.name;

  const awayName =
    data.away?.name ||
    currentFixture.away.name;

  const homeLines =
    data.lines?.home || [];

  const awayLines =
    data.lines?.away || [];

  const homeBest =
    chooseBestTeamLines(
      homeName,
      homeLines
    );

  const awayBest =
    chooseBestTeamLines(
      awayName,
      awayLines
    );

  const opportunities = [
    ...homeBest,
    ...awayBest
  ];

  opportunities.sort(
    (a, b) => {

      /*
        Primeiro maior porcentagem.
      */
      if (b.rate !== a.rate) {
        return b.rate - a.rate;
      }

      /*
        Depois maior quantidade
        de jogos analisados.
      */
      if (b.games !== a.games) {
        return b.games - a.games;
      }

      /*
        Depois maior número
        de acertos.
      */
      if (b.hits !== a.hits) {
        return b.hits - a.hits;
      }

      /*
        Por último linha maior.
      */
      return (
        b.threshold -
        a.threshold
      );
    }
  );

  return opportunities;
}


/* ======================================================
   MOSTRAR MELHORES OPORTUNIDADES
====================================================== */

function renderBestOpportunities(data) {
  let container =
    $("bestOpportunities");

  if (!container) {

    const statsCard =
      analysisPanel
        .querySelectorAll(".card")[1];

    if (!statsCard) {
      return;
    }

    const box =
      document.createElement("div");

    box.className = "card";
    box.id =
      "bestOpportunitiesCard";

    box.style.marginTop = "16px";

    box.innerHTML = `
      <div class="section-head">

        <h2>
          Melhores oportunidades
        </h2>

        <span>
          80%+
        </span>

      </div>

      <p
        class="muted"
        style="
          margin-top:0;
          margin-bottom:16px;
        "
      >
        Melhor linha histórica
        de cada estatística.
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
        As porcentagens representam
        apenas o histórico dos jogos
        analisados. Não garantem que
        a linha acontecerá novamente.
      </div>
    `;

    statsCard.insertAdjacentElement(
      "afterend",
      box
    );

    container =
      $("bestOpportunities");
  }

  const opportunities =
    getBestOpportunities(data);

  if (!opportunities.length) {

    container.innerHTML = `
      <div class="safe-box">
        Nenhuma linha atingiu
        pelo menos 80%
        neste recorte.
      </div>
    `;

    return;
  }

  container.innerHTML =
    opportunities
      .map((item, index) => `

        <div
          class="safe-box"
          style="
            margin-bottom:12px;
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
                ${index + 1}.
                ${item.team}
              </div>

              <strong>
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
                  color:
                  ${lineColor(
                    item.rate
                  )};
                  font-size:18px;
                "
              >
                ${item.rate}%
              </strong>

              <small
                style="
                  display:block;
                  margin-top:2px;
                  opacity:.8;
                "
              >
                ${strengthLabel(
                  item.rate
                )}
              </small>

            </div>

          </div>


          <small
            style="
              display:block;
              margin-top:8px;
              opacity:.75;
            "
          >
            Bateu ${item.hits}
            de ${item.games} jogos
          </small>

        </div>

      `)
      .join("");
}


/* ======================================================
   HISTÓRICO COMPLETO
====================================================== */

function renderTeamLines(
  teamName,
  lines
) {
  if (!lines || !lines.length) {

    return `
      <div class="safe-box">
        <strong>${teamName}</strong>
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

  const realSample =
    Math.min(
      homeUsed,
      awayUsed
    );

  if (!linesContainer) {

    const cards =
      analysisPanel
        .querySelectorAll(".card");

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
          ${realSample}
          jogos encontrados
        </span>

      </div>


      <p
        class="muted"
        style="
          margin-top:0;
          margin-bottom:16px;
        "
      >
        Quantas vezes cada linha
        aconteceu nos jogos
        analisados.
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
        `${realSample} jogos encontrados`;

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

    const data = await getJSON(
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
   BOTÃO ATUALIZAR
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

      document
        .querySelector(".intro")
        .classList.remove(
          "hidden"
        );

      fixturesEl.classList.remove(
        "hidden"
      );

    }
  );


/* ======================================================
   ÚLTIMOS 5 / ÚLTIMOS 10
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
          .forEach(b =>

            b.classList.toggle(
              "active",
              b === btn
            )

          );

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
