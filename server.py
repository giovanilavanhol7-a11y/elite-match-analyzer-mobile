from flask import Flask, jsonify, request, send_from_directory
import os
import requests
import time
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__, static_folder="static")

# =========================================================
# CONFIGURAÇÃO
# =========================================================

API_KEY = os.getenv("PITCHAPI_KEY", "").strip()
API_BASE = "https://api.pitchapi.dev"

TZ_NAME = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")

CACHE = {}

CACHE_FIXTURES = 300
CACHE_ANALYSIS = 900
CACHE_API = 600


# =========================================================
# CACHE
# =========================================================

def cache_get(key):
    item = CACHE.get(key)

    if not item:
        return None

    if time.time() > item["expires"]:
        CACHE.pop(key, None)
        return None

    return item["value"]


def cache_set(key, value, ttl):
    CACHE[key] = {
        "value": value,
        "expires": time.time() + ttl
    }


# =========================================================
# PITCHAPI
# =========================================================

def api_get(path, cache_seconds=CACHE_API):

    if not API_KEY:
        raise RuntimeError(
            "PITCHAPI_KEY não configurada no Render."
        )

    path = path.lstrip("/")

    cache_key = f"api:{path}"

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    url = f"{API_BASE}/{path}"

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
            f"Resposta inválida da PitchAPI "
            f"(HTTP {response.status_code})."
        )

    if not response.ok:

        message = None

        if isinstance(body, dict):

            error = body.get("error")

            if isinstance(error, dict):
                message = (
                    error.get("message")
                    or error.get("code")
                )

            elif error:
                message = str(error)

            if not message:
                message = body.get("message")

        raise RuntimeError(
            message
            or f"Erro HTTP {response.status_code}"
        )

    if isinstance(body, dict) and "data" in body:
        data = body["data"]
    else:
        data = body

    cache_set(
        cache_key,
        data,
        cache_seconds
    )

    return data


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def local_time(value):

    if not value:
        return ""

    try:

        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        dt = dt.astimezone(
            ZoneInfo(TZ_NAME)
        )

        return dt.strftime("%H:%M")

    except Exception:
        return ""


def normalize_fixture(item):

    league = item.get("league") or {}
    home = item.get("home_team") or {}
    away = item.get("away_team") or {}

    return {
        "id": item.get("id"),

        "league": league.get(
            "name",
            "Competição"
        ),

        "league_id": league.get("id"),

        "league_logo": league.get(
            "image_url",
            ""
        ),

        "time": local_time(
            item.get("time_utc")
        ),

        "status": item.get(
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


def safe_number(value):

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if not text:
        return None

    text = text.split(" ")[0]

    text = text.replace("%", "")
    text = text.replace(",", ".")

    try:
        return float(text)

    except Exception:
        return None


# =========================================================
# ESTATÍSTICAS BRUTAS DA PARTIDA
# =========================================================

def extract_team_stats(match_id):

    try:

        data = api_get(
            f"v1/matches/{match_id}/stats"
        )

    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    periods = data.get("periods") or []

    result = {}

    for period in periods:

        period_name = str(
            period.get("period", "")
        ).lower()

        if period_name not in (
            "all",
            "full",
            "match",
            "total",
            "ft"
        ):
            continue

        groups = period.get("groups") or []

        for group in groups:

            items = group.get("items") or []

            for item in items:

                key = str(
                    item.get("key", "")
                ).strip().lower()

                title = str(
                    item.get("title", "")
                ).strip().lower()

                if not key:
                    key = title

                result[key] = {
                    "title": title,

                    "home": safe_number(
                        item.get("home")
                    ),

                    "away": safe_number(
                        item.get("away")
                    )
                }

    return result


def find_stat(stats, aliases):

    aliases = [
        str(x).lower()
        for x in aliases
    ]

    for alias in aliases:

        if alias in stats:
            return stats[alias]

    for key, value in stats.items():

        key_text = str(key).lower()

        title = str(
            value.get("title", "")
        ).lower()

        for alias in aliases:

            if alias == key_text:
                return value

            if alias in key_text:
                return value

            if alias in title:
                return value

    return None


# =========================================================
# JOGOS RECENTES
# =========================================================

def recent_team_matches(
    league_id,
    team_id,
    current_match_id,
    sample
):

    if not league_id or not team_id:
        return []

    try:

        data = api_get(
            f"v1/leagues/{league_id}/matches"
        )

    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    matches = data.get(
        "matches",
        []
    )

    finished = []

    for match in matches:

        if match.get("id") == current_match_id:
            continue

        home = match.get(
            "home_team"
        ) or {}

        away = match.get(
            "away_team"
        ) or {}

        if (
            home.get("id") != team_id
            and away.get("id") != team_id
        ):
            continue

        status = str(
            match.get(
                "status",
                ""
            )
        ).lower()

        if status not in (
            "finished",
            "complete",
            "completed",
            "ft",
            "full_time",
            "full time"
        ):
            continue

        finished.append(match)

    def sort_key(match):

        return (
            match.get("time_utc")
            or match.get("date")
            or ""
        )

    finished.sort(
        key=sort_key,
        reverse=True
    )

    return finished[:sample]


# =========================================================
# DADOS DE UM TIME EM UMA PARTIDA
# =========================================================

def team_match_data(match, team_id):

    match_id = match.get("id")

    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    is_home = home.get("id") == team_id

    score_home = safe_number(
        match.get("score_home")
    )

    score_away = safe_number(
        match.get("score_away")
    )

    goals = (
        score_home
        if is_home
        else score_away
    )

    raw_stats = extract_team_stats(
        match_id
    )

    # ESCANTEIOS
    corners_item = find_stat(
        raw_stats,
        [
            "corners",
            "corner_kicks",
            "corner kicks",
            "corner"
        ]
    )

    # FALTAS
    fouls_item = find_stat(
        raw_stats,
        [
            "fouls",
            "fouls_committed",
            "fouls committed",
            "foul"
        ]
    )

    # FINALIZAÇÕES
    shots_item = find_stat(
        raw_stats,
        [
            "shots",
            "total_shots",
            "total shots",
            "shots total",
            "goal attempts"
        ]
    )

    # CHUTES NO GOL
    sot_item = find_stat(
        raw_stats,
        [
            "shots_on_target",
            "shots on target",
            "on target",
            "shots target"
        ]
    )

    # CARTÕES AMARELOS
    yellow_item = find_stat(
        raw_stats,
        [
            "yellow_cards",
            "yellow cards",
            "yellow card"
        ]
    )

    # CARTÕES VERMELHOS
    red_item = find_stat(
        raw_stats,
        [
            "red_cards",
            "red cards",
            "red card"
        ]
    )

    def side_value(item):

        if not item:
            return None

        if is_home:
            return item.get("home")

        return item.get("away")

    corners = side_value(
        corners_item
    )

    fouls = side_value(
        fouls_item
    )

    shots = side_value(
        shots_item
    )

    sot = side_value(
        sot_item
    )

    yellow = side_value(
        yellow_item
    )

    red = side_value(
        red_item
    )

    cards = None

    if (
        yellow is not None
        or red is not None
    ):

        cards = (
            (yellow or 0)
            + (red or 0)
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
# MÉDIAS
# =========================================================

def average(values):

    valid = [
        float(value)
        for value in values
        if value is not None
    ]

    if not valid:
        return None

    return round(
        sum(valid) / len(valid),
        2
    )


def team_averages(
    league_id,
    team_id,
    current_match_id,
    sample
):

    matches = recent_team_matches(
        league_id,
        team_id,
        current_match_id,
        sample
    )

    collection = {
        "goals": [],
        "corners": [],
        "shots": [],
        "sot": [],
        "cards": [],
        "fouls": []
    }

    for match in matches:

        data = team_match_data(
            match,
            team_id
        )

        for key in collection:

            collection[key].append(
                data.get(key)
            )

    averages = {
        key: average(values)
        for key, values
        in collection.items()
    }

    coverage = {
        key: len(
            [
                value
                for value in values
                if value is not None
            ]
        )
        for key, values
        in collection.items()
    }

    return {
        "matches_used": len(matches),
        "averages": averages,
        "coverage": coverage
    }


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
        "provider": "PITCHAPI",

        "api_configured": bool(
            API_KEY
        ),

        "demo_mode": False,

        "timezone": TZ_NAME
    })


# =========================================================
# JOGOS DE HOJE
# =========================================================

@app.get("/api/fixtures/today")
def fixtures_today():

    cached = cache_get(
        "fixtures_today"
    )

    if cached is not None:
        return jsonify(cached)

    if not API_KEY:

        return jsonify({
            "mode": "error",

            "message":
                "PITCHAPI_KEY não configurada.",

            "fixtures": []
        }), 500

    try:

        today = datetime.now(
            ZoneInfo(TZ_NAME)
        ).strftime(
            "%Y-%m-%d"
        )

        data = api_get(
            f"v1/date/{today}",
            300
        )

        matches = []

        if isinstance(data, dict):

            matches = data.get(
                "matches",
                []
            )

        fixtures = [
            normalize_fixture(match)
            for match in matches
        ]

        response = {
            "mode": "live",
            "message": "",
            "fixtures": fixtures
        }

        cache_set(
            "fixtures_today",
            response,
            CACHE_FIXTURES
        )

        return jsonify(
            response
        )

    except Exception as e:

        return jsonify({
            "mode": "error",
            "message": str(e),
            "fixtures": []
        }), 502


# =========================================================
# TESTE DA API
# =========================================================

@app.get("/api/test-pitch")
def test_pitch():

    try:

        today = datetime.now(
            ZoneInfo(TZ_NAME)
        ).strftime(
            "%Y-%m-%d"
        )

        data = api_get(
            f"v1/date/{today}",
            60
        )

        matches = []

        if isinstance(data, dict):

            matches = data.get(
                "matches",
                []
            )

        return jsonify({
            "ok": True,

            "provider":
                "PITCHAPI",

            "date":
                today,

            "matches_found":
                len(matches),

            "sample":
                matches[:3]
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 502


# =========================================================
# DETALHES DO JOGO
# =========================================================

@app.get("/api/match/<fixture_id>")
def match_detail(fixture_id):

    try:

        data = api_get(
            f"v1/matches/{fixture_id}"
        )

        return jsonify({
            "ok": True,
            "data": data
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 502


# =========================================================
# ESTATÍSTICAS BRUTAS
# =========================================================

@app.get("/api/match/<fixture_id>/stats")
def match_stats(fixture_id):

    try:

        data = api_get(
            f"v1/matches/{fixture_id}/stats"
        )

        return jsonify({
            "ok": True,
            "data": data
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 502


# =========================================================
# CHUTES BRUTOS
# =========================================================

@app.get("/api/match/<fixture_id>/shots")
def match_shots(fixture_id):

    try:

        data = api_get(
            f"v1/matches/{fixture_id}/shots"
        )

        return jsonify({
            "ok": True,
            "data": data
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 502


# =========================================================
# EVENTOS
# =========================================================

@app.get("/api/match/<fixture_id>/events")
def match_events(fixture_id):

    try:

        data = api_get(
            f"v1/matches/{fixture_id}/events"
        )

        return jsonify({
            "ok": True,
            "data": data
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 502


# =========================================================
# ANÁLISE DOS ÚLTIMOS 5 / 10
# =========================================================

@app.get("/api/analysis/<fixture_id>")
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

    if sample not in (5, 10):
        sample = 10

    cache_key = (
        f"analysis:"
        f"{fixture_id}:"
        f"{sample}"
    )

    cached = cache_get(
        cache_key
    )

    if cached is not None:

        return jsonify(
            cached
        )

    try:

        fixture = api_get(
            f"v1/matches/{fixture_id}"
        )

        if not isinstance(
            fixture,
            dict
        ):

            raise RuntimeError(
                "Partida não encontrada."
            )

        league = fixture.get(
            "league"
        ) or {}

        home = fixture.get(
            "home_team"
        ) or {}

        away = fixture.get(
            "away_team"
        ) or {}

        league_id = league.get(
            "id"
        )

        home_id = home.get(
            "id"
        )

        away_id = away.get(
            "id"
        )

        home_data = team_averages(
            league_id,
            home_id,
            fixture_id,
            sample
        )

        away_data = team_averages(
            league_id,
            away_id,
            fixture_id,
            sample
        )

        h = home_data[
            "averages"
        ]

        a = away_data[
            "averages"
        ]

        stats = [
            {
                "key": "goals",
                "label": "Gols",
                "home": h.get("goals"),
                "away": a.get("goals")
            },

            {
                "key": "corners",
                "label": "Escanteios",
                "home": h.get("corners"),
                "away": a.get("corners")
            },

            {
                "key": "shots",
                "label": "Finalizações",
                "home": h.get("shots"),
                "away": a.get("shots")
            },

            {
                "key": "sot",
                "label": "Chutes no gol",
                "home": h.get("sot"),
                "away": a.get("sot")
            },

            {
                "key": "cards",
                "label": "Cartões",
                "home": h.get("cards"),
                "away": a.get("cards")
            },

            {
                "key": "fouls",
                "label": "Faltas",
                "home": h.get("fouls"),
                "away": a.get("fouls")
            }
        ]

        response = {
            "source":
                "PITCHAPI",

            "sample_size":
                sample,

            "home": {
                "id":
                    home_id,

                "name":
                    home.get(
                        "name",
                        "Mandante"
                    ),

                "logo":
                    home.get(
                        "image_url",
                        ""
                    ),

                "matches_used":
                    home_data[
                        "matches_used"
                    ],

                "coverage":
                    home_data[
                        "coverage"
                    ]
            },

            "away": {
                "id":
                    away_id,

                "name":
                    away.get(
                        "name",
                        "Visitante"
                    ),

                "logo":
                    away.get(
                        "image_url",
                        ""
                    ),

                "matches_used":
                    away_data[
                        "matches_used"
                    ],

                "coverage":
                    away_data[
                        "coverage"
                    ]
            },

            "stats":
                stats
        }

        cache_set(
            cache_key,
            response,
            CACHE_ANALYSIS
        )

        return jsonify(
            response
        )

    except Exception as e:

        return jsonify({
            "source":
                "PITCHAPI",

            "sample_size":
                sample,

            "stats":
                [],

            "error":
                str(e)
        }), 502


# =========================================================
# LINHAS DE APOSTA
# =========================================================

@app.get("/api/lines/<fixture_id>")
def lines(fixture_id):

    return jsonify({
        "message":
            "As sugestões serão ativadas "
            "depois que validarmos todas as médias.",

        "lines": []
    })


# =========================================================
# INICIAR SERVIDOR
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
        port=port,
        debug=False
    )
