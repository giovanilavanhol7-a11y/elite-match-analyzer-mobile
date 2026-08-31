from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import requests

app = Flask(__name__, static_folder="static")

API_KEY = os.getenv("PITCHAPI_KEY", "").strip()
API_BASE = "https://api.pitchapi.dev"
TIMEZONE = "America/Sao_Paulo"


# =========================================================
# API
# =========================================================

def api_get(path):
    if not API_KEY:
        raise RuntimeError(
            "PITCHAPI_KEY não configurada."
        )

    url = (
        API_BASE
        + "/"
        + path.lstrip("/")
    )

    response = requests.get(
        url,
        headers={
            "X-API-KEY": API_KEY,
            "Accept": "application/json"
        },
        timeout=30
    )

    try:
        body = response.json()

    except Exception:
        raise RuntimeError(
            f"Resposta inválida da API. "
            f"HTTP {response.status_code}"
        )

    if not response.ok:
        raise RuntimeError(
            str(body)
        )

    if (
        isinstance(body, dict)
        and "data" in body
    ):
        return body["data"]

    return body


# =========================================================
# AUXILIARES
# =========================================================

def number(value):
    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):
        return float(value)

    text = str(
        value
    ).strip()

    if not text:
        return None

    text = text.split(" ")[0]
    text = text.replace("%", "")
    text = text.replace(",", ".")

    try:
        return float(text)

    except Exception:
        return None


def average(values):
    valid = [
        float(v)
        for v in values
        if v is not None
    ]

    if not valid:
        return None

    return round(
        sum(valid) / len(valid),
        2
    )


def match_time(value):
    if not value:
        return ""

    try:
        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

        dt = dt.astimezone(
            ZoneInfo(TIMEZONE)
        )

        return dt.strftime(
            "%H:%M"
        )

    except Exception:
        return ""


def normalize_name(value):
    return (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


# =========================================================
# NORMALIZAR PARTIDA
# =========================================================

def normalize_match(match):
    league = (
        match.get("league")
        or {}
    )

    home = (
        match.get("home_team")
        or {}
    )

    away = (
        match.get("away_team")
        or {}
    )

    return {
        "id": match.get("id"),

        "league": league.get(
            "name",
            "Competição"
        ),

        "league_id": league.get(
            "id"
        ),

        "league_logo": league.get(
            "image_url",
            ""
        ),

        "time": match_time(
            match.get("time_utc")
        ),

        "status": match.get(
            "status",
            ""
        ),

        "home": {
            "id": home.get("id"),

            "name": home.get(
                "name",
                "Mandante"
            ),

            "logo": home.get(
                "image_url",
                ""
            )
        },

        "away": {
            "id": away.get("id"),

            "name": away.get(
                "name",
                "Visitante"
            ),

            "logo": away.get(
                "image_url",
                ""
            )
        },

        "demo": False
    }


# =========================================================
# ESTATÍSTICAS OFICIAIS
# =========================================================

def get_stats(match_id):
    try:
        data = api_get(
            f"v1/matches/"
            f"{match_id}/stats"
        )

    except Exception:
        return []

    if not isinstance(
        data,
        dict
    ):
        return []

    result = []

    for period in (
        data.get("periods")
        or []
    ):

        period_name = str(
            period.get(
                "period",
                ""
            )
        ).strip().lower()

        if period_name != "all":
            continue

        for group in (
            period.get("groups")
            or []
        ):

            for item in (
                group.get("items")
                or []
            ):

                result.append({
                    "key": str(
                        item.get(
                            "key",
                            ""
                        )
                    ).strip().lower(),

                    "title": str(
                        item.get(
                            "title",
                            ""
                        )
                    ).strip().lower(),

                    "home": number(
                        item.get("home")
                    ),

                    "away": number(
                        item.get("away")
                    )
                })

    return result


def find_exact_stat(
    stats,
    names,
    home_side
):
    wanted = {
        normalize_name(name)
        for name in names
    }

    for item in stats:

        key = normalize_name(
            item.get("key")
        )

        title = normalize_name(
            item.get("title")
        )

        if (
            key in wanted
            or title in wanted
        ):

            if home_side:
                return item.get(
                    "home"
                )

            return item.get(
                "away"
            )

    return None


# =========================================================
# FINALIZAÇÕES
# =========================================================

def shot_events(
    match_id,
    team_id
):
    try:
        data = api_get(
            f"v1/matches/"
            f"{match_id}/shots"
        )

    except Exception:
        return None

    if not isinstance(
        data,
        dict
    ):
        return None

    periods = data.get(
        "periods"
    )

    if periods is None:
        return None

    total = 0
    found = False

    for period in periods:

        for shot in (
            period.get("shots")
            or []
        ):

            if (
                shot.get("team_id")
                != team_id
            ):
                continue

            found = True
            total += 1

    if not found:
        return None

    return float(total)


# =========================================================
# CHUTES NO GOL
# =========================================================

def sot_from_shots(
    match_id,
    team_id
):
    try:
        data = api_get(
            f"v1/matches/"
            f"{match_id}/shots"
        )

    except Exception:
        return None

    if not isinstance(
        data,
        dict
    ):
        return None

    periods = data.get(
        "periods"
    )

    if periods is None:
        return None

    total = 0
    found = False

    for period in periods:

        for shot in (
            period.get("shots")
            or []
        ):

            if (
                shot.get("team_id")
                != team_id
            ):
                continue

            found = True

            event_type = (
                str(
                    shot.get(
                        "event_type",
                        ""
                    )
                )
                .strip()
                .lower()
                .replace("_", "")
                .replace(" ", "")
                .replace("-", "")
            )

            if event_type in (
                "goal",
                "attemptsaved"
            ):
                total += 1

    if not found:
        return None

    return float(total)


# =========================================================
# CARTÕES
# =========================================================

def get_cards(
    match_id,
    team_id
):
    try:
        data = api_get(
            f"v1/matches/"
            f"{match_id}/events"
        )

    except Exception:
        return None

    if not isinstance(
        data,
        dict
    ):
        return None

    events = data.get(
        "events"
    )

    if events is None:
        return None

    total = 0

    for event in events:

        if (
            event.get("team_id")
            != team_id
        ):
            continue

        event_type = (
            str(
                event.get(
                    "event_type",
                    ""
                )
            )
            .strip()
            .lower()
            .replace("_", "")
            .replace(" ", "")
            .replace("-", "")
        )

        if event_type in (
            "yellowcard",
            "redcard"
        ):
            total += 1

    return float(total)


# =========================================================
# ÚLTIMOS JOGOS
# =========================================================

def recent_matches(
    league_id,
    team_id,
    current_id,
    limit,
    venue
):
    try:
        data = api_get(
            f"v1/leagues/"
            f"{league_id}/matches"
        )

    except Exception:
        return []

    if not isinstance(
        data,
        dict
    ):
        return []

    result = []

    for match in (
        data.get("matches")
        or []
    ):

        if (
            match.get("id")
            == current_id
        ):
            continue

        home = (
            match.get("home_team")
            or {}
        )

        away = (
            match.get("away_team")
            or {}
        )

        # ==========================================
        # CASA / FORA
        # ==========================================

        if venue == "home":

            if (
                home.get("id")
                != team_id
            ):
                continue

        elif venue == "away":

            if (
                away.get("id")
                != team_id
            ):
                continue

        else:

            if (
                home.get("id")
                != team_id
                and
                away.get("id")
                != team_id
            ):
                continue

        status = str(
            match.get(
                "status",
                ""
            )
        ).strip().lower()

        if status not in (
            "finished",
            "complete",
            "completed",
            "ft",
            "full_time",
            "full time"
        ):
            continue

        result.append(
            match
        )

    result.sort(
        key=lambda x: (
            x.get("time_utc")
            or
            x.get("date")
            or
            ""
        ),
        reverse=True
    )

    return result[:limit]


# =========================================================
# DADOS DE UMA EQUIPE EM UMA PARTIDA
# =========================================================

def team_match_values(
    match,
    team_id
):
    match_id = match.get(
        "id"
    )

    home = (
        match.get("home_team")
        or {}
    )

    home_side = (
        home.get("id")
        == team_id
    )

    if home_side:

        goals = number(
            match.get(
                "score_home"
            )
        )

    else:

        goals = number(
            match.get(
                "score_away"
            )
        )

    stats = get_stats(
        match_id
    )

    corners = find_exact_stat(
        stats,
        [
            "corners",
            "corner_kicks",
            "corner kicks"
        ],
        home_side
    )

    fouls = find_exact_stat(
        stats,
        [
            "fouls",
            "fouls_committed",
            "fouls committed"
        ],
        home_side
    )

    shots = find_exact_stat(
        stats,
        [
            "shots",
            "total_shots",
            "total shots"
        ],
        home_side
    )

    if shots is None:

        shots = shot_events(
            match_id,
            team_id
        )

    sot = find_exact_stat(
        stats,
        [
            "shots_on_target",
            "shots on target"
        ],
        home_side
    )

    if sot is None:

        sot = sot_from_shots(
            match_id,
            team_id
        )

    cards = get_cards(
        match_id,
        team_id
    )

    return {
        "goals": goals,
        "corners": corners,
        "shots": shots,
        "sot": sot,
        "cards": cards,
        "fouls": fouls
    }


# =========================================================
# DESCOBRIR ADVERSÁRIO
# =========================================================

def opponent_id_from_match(
    match,
    team_id
):
    home = (
        match.get("home_team")
        or {}
    )

    away = (
        match.get("away_team")
        or {}
    )

    if (
        home.get("id")
        == team_id
    ):
        return away.get("id")

    if (
        away.get("id")
        == team_id
    ):
        return home.get("id")

    return None


# =========================================================
# MÉDIA DO TIME
#
# PRODUCED:
# o que o próprio time fez.
#
# CONCEDED:
# o que os adversários fizeram contra ele.
# =========================================================

def team_average(
    league_id,
    team_id,
    current_id,
    limit,
    venue
):
    matches = recent_matches(
        league_id,
        team_id,
        current_id,
        limit,
        venue
    )

    produced = {
        "goals": [],
        "corners": [],
        "shots": [],
        "sot": [],
        "cards": [],
        "fouls": []
    }

    conceded = {
        "goals": [],
        "corners": [],
        "shots": [],
        "sot": [],
        "cards": [],
        "fouls": []
    }

    history = []

    for match in matches:

        # ==========================================
        # O QUE O TIME PRODUZIU
        # ==========================================

        own_row = team_match_values(
            match,
            team_id
        )

        # ==========================================
        # QUEM ERA O ADVERSÁRIO
        # ==========================================

        opponent_id = (
            opponent_id_from_match(
                match,
                team_id
            )
        )

        # ==========================================
        # O QUE O ADVERSÁRIO PRODUZIU
        # CONTRA O TIME
        # =
        # O QUE O TIME CEDEU
        # ==========================================

        if opponent_id:

            conceded_row = (
                team_match_values(
                    match,
                    opponent_id
                )
            )

        else:

            conceded_row = {
                "goals": None,
                "corners": None,
                "shots": None,
                "sot": None,
                "cards": None,
                "fouls": None
            }

        for key in produced:

            produced[key].append(
                own_row.get(key)
            )

            conceded[key].append(
                conceded_row.get(key)
            )

        home = (
            match.get("home_team")
            or {}
        )

        away = (
            match.get("away_team")
            or {}
        )

        history.append({
            "match_id": match.get(
                "id"
            ),

            "home": home.get(
                "name",
                ""
            ),

            "away": away.get(
                "name",
                ""
            ),

            "produced": own_row,

            "conceded": conceded_row
        })

    return {
        "matches_used": len(matches),

        "venue": venue,

        # ==========================================
        # COMPATIBILIDADE COM O APP ATUAL
        # ==========================================

        "averages": {
            key: average(value)
            for key, value
            in produced.items()
        },

        "coverage": {
            key: len([
                x
                for x in value
                if x is not None
            ])
            for key, value
            in produced.items()
        },

        "values": produced,

        # ==========================================
        # NOVOS DADOS: CONCEDIDOS
        # ==========================================

        "conceded_averages": {
            key: average(value)
            for key, value
            in conceded.items()
        },

        "conceded_coverage": {
            key: len([
                x
                for x in value
                if x is not None
            ])
            for key, value
            in conceded.items()
        },

        "conceded_values": conceded,

        "history": history
    }


# =========================================================
# CONTAGEM DE LINHAS
# =========================================================

def line_result(
    values,
    threshold
):
    valid = [
        float(v)
        for v in values
        if v is not None
    ]

    if not valid:

        return {
            "line": threshold,
            "hits": 0,
            "games": 0,
            "rate": None
        }

    hits = sum(
        1
        for value in valid
        if value > threshold
    )

    rate = round(
        hits
        / len(valid)
        * 100,
        1
    )

    return {
        "line": threshold,
        "hits": hits,
        "games": len(valid),
        "rate": rate
    }


# =========================================================
# DEFINIÇÃO DAS LINHAS
# =========================================================

LINE_DEFINITIONS = [
    (
        "goals",
        "+0.5 Gols",
        0.5
    ),

    (
        "corners",
        "+3.5 Escanteios",
        3.5
    ),

    (
        "corners",
        "+4.5 Escanteios",
        4.5
    ),

    (
        "shots",
        "+9.5 Finalizações",
        9.5
    ),

    (
        "shots",
        "+12.5 Finalizações",
        12.5
    ),

    (
        "sot",
        "+2.5 Chutes no gol",
        2.5
    ),

    (
        "sot",
        "+3.5 Chutes no gol",
        3.5
    ),

    (
        "cards",
        "+0.5 Cartões",
        0.5
    ),

    (
        "cards",
        "+1.5 Cartões",
        1.5
    ),

    (
        "fouls",
        "+9.5 Faltas",
        9.5
    ),

    (
        "fouls",
        "+10.5 Faltas",
        10.5
    )
]


# =========================================================
# CRIAR LINHAS A PARTIR DOS VALORES
# =========================================================

def build_lines_from_values(
    values
):
    result = []

    for (
        metric,
        label,
        threshold
    ) in LINE_DEFINITIONS:

        result.append({
            "metric": metric,
            "label": label,

            **line_result(
                values.get(
                    metric,
                    []
                ),
                threshold
            )
        })

    return result


def build_lines(team_data):
    return build_lines_from_values(
        team_data["values"]
    )


def build_conceded_lines(
    team_data
):
    return build_lines_from_values(
        team_data[
            "conceded_values"
        ]
    )


# =========================================================
# CRUZAMENTO PRODUZ X ADVERSÁRIO CEDE
# =========================================================

def build_cross_lines(
    produced_team,
    opponent_team
):
    result = []

    produced_values = (
        produced_team["values"]
    )

    opponent_conceded = (
        opponent_team[
            "conceded_values"
        ]
    )

    produced_avg = (
        produced_team[
            "averages"
        ]
    )

    conceded_avg = (
        opponent_team[
            "conceded_averages"
        ]
    )

    for (
        metric,
        label,
        threshold
    ) in LINE_DEFINITIONS:

        own_result = line_result(
            produced_values.get(
                metric,
                []
            ),
            threshold
        )

        conceded_result = (
            line_result(
                opponent_conceded.get(
                    metric,
                    []
                ),
                threshold
            )
        )

        own_rate = own_result.get(
            "rate"
        )

        conceded_rate = (
            conceded_result.get(
                "rate"
            )
        )

        # ==========================================
        # MÉDIA SIMPLES DAS DUAS TENDÊNCIAS
        #
        # NÃO É PROBABILIDADE.
        # É SÓ UM ÍNDICE HISTÓRICO
        # PARA ORDENAR O CRUZAMENTO.
        # ==========================================

        rates = [
            value
            for value in (
                own_rate,
                conceded_rate
            )
            if value is not None
        ]

        if rates:

            cross_rate = round(
                sum(rates)
                / len(rates),
                1
            )

        else:
            cross_rate = None

        averages = [
            value
            for value in (
                produced_avg.get(
                    metric
                ),
                conceded_avg.get(
                    metric
                )
            )
            if value is not None
        ]

        if averages:

            cross_average = round(
                sum(averages)
                / len(averages),
                2
            )

        else:
            cross_average = None

        result.append({
            "metric": metric,

            "label": label,

            "line": threshold,

            # TIME PRODUZ
            "produced": {
                "average":
                    produced_avg.get(
                        metric
                    ),

                "hits":
                    own_result[
                        "hits"
                    ],

                "games":
                    own_result[
                        "games"
                    ],

                "rate":
                    own_rate
            },

            # ADVERSÁRIO CEDE
            "opponent_conceded": {
                "average":
                    conceded_avg.get(
                        metric
                    ),

                "hits":
                    conceded_result[
                        "hits"
                    ],

                "games":
                    conceded_result[
                        "games"
                    ],

                "rate":
                    conceded_rate
            },

            # ÍNDICE DO CRUZAMENTO
            "cross_average":
                cross_average,

            "cross_rate":
                cross_rate
        })

    return result


# =========================================================
# SITE
# =========================================================

@app.get("/")
def index():
    return send_from_directory(
        "static",
        "index.html"
    )


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,

        "provider":
            "PITCHAPI",

        "api_configured":
            bool(API_KEY),

        "demo_mode":
            False,

        "timezone":
            TIMEZONE,

        "version":
            "CROSS-V1"
    })


# =========================================================
# PARTIDAS DE HOJE
# =========================================================

@app.get("/api/fixtures/today")
def fixtures_today():
    try:

        today = datetime.now(
            ZoneInfo(TIMEZONE)
        ).strftime(
            "%Y-%m-%d"
        )

        data = api_get(
            f"v1/date/{today}"
        )

        matches = []

        if isinstance(
            data,
            dict
        ):

            matches = (
                data.get("matches")
                or []
            )

        return jsonify({
            "mode": "live",

            "message": "",

            "fixtures": [
                normalize_match(
                    match
                )
                for match
                in matches
            ]
        })

    except Exception as error:

        return jsonify({
            "mode": "error",

            "message":
                str(error),

            "fixtures": []
        }), 502


# =========================================================
# ANÁLISE
# =========================================================

@app.get(
    "/api/analysis/<fixture_id>"
)
def analysis(fixture_id):

    try:
        sample = int(
            request.args.get(
                "sample",
                10
            )
        )

    except Exception:
        sample = 10

    if sample not in (
        5,
        10
    ):
        sample = 10

    try:

        fixture = api_get(
            f"v1/matches/"
            f"{fixture_id}"
        )

        if not isinstance(
            fixture,
            dict
        ):
            raise RuntimeError(
                "Partida não encontrada."
            )

        league = (
            fixture.get("league")
            or {}
        )

        home = (
            fixture.get("home_team")
            or {}
        )

        away = (
            fixture.get("away_team")
            or {}
        )

        league_id = league.get(
            "id"
        )

        home_id = home.get(
            "id"
        )

        away_id = away.get(
            "id"
        )

        # ==========================================
        # MANDANTE
        # SOMENTE JOGOS EM CASA
        # ==========================================

        home_data = team_average(
            league_id,
            home_id,
            fixture_id,
            sample,
            "home"
        )

        # ==========================================
        # VISITANTE
        # SOMENTE JOGOS FORA
        # ==========================================

        away_data = team_average(
            league_id,
            away_id,
            fixture_id,
            sample,
            "away"
        )

        h = home_data[
            "averages"
        ]

        a = away_data[
            "averages"
        ]

        home_conceded = (
            home_data[
                "conceded_averages"
            ]
        )

        away_conceded = (
            away_data[
                "conceded_averages"
            ]
        )

        # ==========================================
        # CRUZAMENTO
        #
        # HOME:
        # mandante produz
        # x
        # visitante concede fora
        #
        # AWAY:
        # visitante produz fora
        # x
        # mandante concede em casa
        # ==========================================

        home_cross = (
            build_cross_lines(
                home_data,
                away_data
            )
        )

        away_cross = (
            build_cross_lines(
                away_data,
                home_data
            )
        )

        return jsonify({
            "source":
                "PITCHAPI",

            "version":
                "CROSS-V1",

            "sample_size":
                sample,

            "home": {
                "id": home_id,

                "name": home.get(
                    "name",
                    "Mandante"
                ),

                "logo": home.get(
                    "image_url",
                    ""
                ),

                "venue":
                    "home",

                "matches_used":
                    home_data[
                        "matches_used"
                    ],

                "coverage":
                    home_data[
                        "coverage"
                    ],

                # NOVO
                "averages": h,

                # NOVO
                "conceded":
                    home_conceded,

                # NOVO
                "conceded_coverage":
                    home_data[
                        "conceded_coverage"
                    ]
            },

            "away": {
                "id": away_id,

                "name": away.get(
                    "name",
                    "Visitante"
                ),

                "logo": away.get(
                    "image_url",
                    ""
                ),

                "venue":
                    "away",

                "matches_used":
                    away_data[
                        "matches_used"
                    ],

                "coverage":
                    away_data[
                        "coverage"
                    ],

                # NOVO
                "averages": a,

                # NOVO
                "conceded":
                    away_conceded,

                # NOVO
                "conceded_coverage":
                    away_data[
                        "conceded_coverage"
                    ]
            },

            # ==========================================
            # MÉDIAS QUE JÁ APARECEM NO SITE
            # ==========================================

            "stats": [
                {
                    "label":
                        "Gols",

                    "home":
                        h["goals"],

                    "away":
                        a["goals"]
                },

                {
                    "label":
                        "Escanteios",

                    "home":
                        h["corners"],

                    "away":
                        a["corners"]
                },

                {
                    "label":
                        "Finalizações",

                    "home":
                        h["shots"],

                    "away":
                        a["shots"]
                },

                {
                    "label":
                        "Chutes no gol",

                    "home":
                        h["sot"],

                    "away":
                        a["sot"]
                },

                {
                    "label":
                        "Cartões",

                    "home":
                        h["cards"],

                    "away":
                        a["cards"]
                },

                {
                    "label":
                        "Faltas",

                    "home":
                        h["fouls"],

                    "away":
                        a["fouls"]
                }
            ],

            # ==========================================
            # LINHAS ANTIGAS
            # CONTINUAM FUNCIONANDO
            # ==========================================

            "lines": {
                "home":
                    build_lines(
                        home_data
                    ),

                "away":
                    build_lines(
                        away_data
                    )
            },

            # ==========================================
            # NOVO:
            # LINHAS QUE CADA EQUIPE CEDEU
            # ==========================================

            "conceded_lines": {
                "home":
                    build_conceded_lines(
                        home_data
                    ),

                "away":
                    build_conceded_lines(
                        away_data
                    )
            },

            # ==========================================
            # NOVO:
            # PRODUZ X ADVERSÁRIO CEDE
            # ==========================================

            "cross": {
                "home": home_cross,
                "away": away_cross
            }
        })

    except Exception as error:

        return jsonify({
            "source":
                "PITCHAPI",

            "version":
                "CROSS-V1",

            "sample_size":
                sample,

            "stats": [],

            "lines": {},

            "conceded_lines": {},

            "cross": {},

            "error":
                str(error)
        }), 502


# =========================================================
# LINHAS
# =========================================================

@app.get(
    "/api/lines/<fixture_id>"
)
def lines(fixture_id):

    try:
        sample = int(
            request.args.get(
                "sample",
                10
            )
        )

    except Exception:
        sample = 10

    if sample not in (
        5,
        10
    ):
        sample = 10

    try:

        fixture = api_get(
            f"v1/matches/"
            f"{fixture_id}"
        )

        league = (
            fixture.get("league")
            or {}
        )

        home = (
            fixture.get("home_team")
            or {}
        )

        away = (
            fixture.get("away_team")
            or {}
        )

        league_id = league.get(
            "id"
        )

        home_data = team_average(
            league_id,
            home.get("id"),
            fixture_id,
            sample,
            "home"
        )

        away_data = team_average(
            league_id,
            away.get("id"),
            fixture_id,
            sample,
            "away"
        )

        return jsonify({
            "sample_size":
                sample,

            "version":
                "CROSS-V1",

            "home": {
                "name": home.get(
                    "name",
                    "Mandante"
                ),

                "venue":
                    "home",

                "matches_used":
                    home_data[
                        "matches_used"
                    ],

                "lines":
                    build_lines(
                        home_data
                    ),

                "conceded_lines":
                    build_conceded_lines(
                        home_data
                    )
            },

            "away": {
                "name": away.get(
                    "name",
                    "Visitante"
                ),

                "venue":
                    "away",

                "matches_used":
                    away_data[
                        "matches_used"
                    ],

                "lines":
                    build_lines(
                        away_data
                    ),

                "conceded_lines":
                    build_conceded_lines(
                        away_data
                    )
            },

            "cross": {
                "home":
                    build_cross_lines(
                        home_data,
                        away_data
                    ),

                "away":
                    build_cross_lines(
                        away_data,
                        home_data
                    )
            }
        })

    except Exception as error:

        return jsonify({
            "error":
                str(error)
        }), 502


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
