const $ = (id) => document.getElementById(id);

const fixturesEl = $("fixtures");
const notice = $("notice");
const analysisPanel = $("analysisPanel");

let currentFixture = null;
let currentSample = 10;


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

      btn.addEventListener(
        "click",
        () => {
          const item = items.find(
            x =>
              String(x.id) ===
              btn.dataset.id
          );

          openAnalysis(item);
        }
      );

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


function setBigTeam(
  prefix,
  team
) {
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


function lineColor(rate) {
  if (rate === null) {
    return "var(--muted)";
  }

  if (rate >= 80) {
    return "var(--green)";
  }

  if (rate >= 60) {
    return "var(--amber)";
  }

  return "var(--muted)";
}


function renderTeamLines(
  teamName,
  lines
) {
  if (!lines || !lines.length) {
    return `
      <div class="safe-box">
        <strong>${teamName}</strong>
        <p>Sem dados suficientes.</p>
      </div>
    `;
  }

  return `
    <div
      class="safe-box"
      style="margin-bottom:14px"
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
                    ${lineColor(line.rate)}
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


function renderLines(data) {
  let linesContainer =
    $("linesResults");

  if (!linesContainer) {

    const automaticSection =
      analysisPanel
        .querySelectorAll(
          ".card"
        )[2];

    if (!automaticSection) {
      return;
    }

    automaticSection.innerHTML = `
      <div class="section-head">
        <h2>
          Histórico das linhas
        </h2>

        <span>
          Últimos ${currentSample}
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

      <div id="linesResults"></div>
    `;

    linesContainer =
      $("linesResults");
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
              ${formatStat(s.home)}
            </div>

            <div class="stat-label">
              ${s.label}
            </div>

            <div class="stat-value">
              ${formatStat(s.away)}
            </div>

          </div>
        `)
        .join("") ||
      `
        <div class="empty">
          Sem estatísticas disponíveis.
        </div>
      `;

    renderLines(data);

  } catch (error) {

    $("statsList").innerHTML = `
      <div class="empty error">
        ${error.message}
      </div>
    `;
  }
}


$("refreshBtn")
  .addEventListener(
    "click",
    loadFixtures
  );


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


loadFixtures();
