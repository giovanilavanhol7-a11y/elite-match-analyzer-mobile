from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import time
import requests

app = Flask(__name__, static_folder="static")

API_KEY = os.getenv("PITCHAPI_KEY", "").strip()
API_BASE = "https://api.pitchapi.dev"
TIMEZONE = "America/Sao_Paulo"

CACHE = {}


# =========================================================
# CACHE
# =========================================================

def cache_get(key):
    item = CACHE.get(key)

    if not item:
        return None

    if item["expires"] < time.time():
        CACHE.pop(key, None)
        return None

    return item["data"]


def cache_set(key, data, seconds=600):
    CACHE[key] = {
        "data": data,
        "expires": time.time() + seconds
    }


# =========================================================
# API
# =========================================================

def api_get(path):
    if not API_KEY:
        raise RuntimeError("PITCHAPI_KEY não configurada.")

    key = "api:" + path

    cached = cache_get(key)

    if cached is not None:
        return cached

    url = API_BASE + "/" + path.lstrip("/")

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
            f"Resposta inválida da API. HTTP {response.status_code}"
        )

    if not response.ok:
        message = None

        if isinstance(body, dict):
            message = (
                body.get("message")
                or body.get("error")
            )

        raise RuntimeError(
            str(message or body)
        )

    if isinstance(body, dict) and "data" in body:
        data = body["data"]
    else:
        data = body

    cache_set(key, data)

    return data


# =========================================================
# AUXILIARES
# =========================================================

def number(value):
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
            value.replace("Z", "+00:00")
        )

        dt = dt.astimezone(
            ZoneInfo(TIMEZONE)
        )

        return dt.strftime("%H:%M")

    except Exception:
        return ""


# =========================================================
# NORMALIZAR JOGO
# =========================================================

def normalize_match(match):
    league = match.get("league") or {}
    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    return {
        "id": match.get("id"),

        "league": league.get(
            "name",
            "Competição"
        ),

        "league_id": league.get("id"),

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
# STATS
# =========================================================

def get_stats(match_id):
    try:
        data = api_get(
            f"v1/matches/{match_id}/stats"
        )
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    result = {}

    for period in data.get("periods") or []:

        period_name = str(
            period.get("period", "")
        ).lower()

        if period_name not in (
            "all",
            "full",
            "match",
            "total"
        ):
            continue

        for group in period.get("groups") or []:

            for item in group.get("items") or []:

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
                    "home": number(
                        item.get("home")
                    ),
                    "away": number(
                        item.get("away")
                    )
                }

    return result


def exact_stat(stats, keys, home_side):
    for key in keys:

        item = stats.get(
            key.lower()
        )

        if item:
            return (
                item.get("home")
                if home_side
                else item.get("away")
            )

    return None


# =========================================================
# FINALIZAÇÕES E CHUTES NO GOL
# =========================================================

def get_shots(match_id, team_id):
    try:
        data = api_get(
            f"v1/matches/{match_id}/shots"
        )

    except Exception:
        return {
            "shots": None,
            "sot": None
        }

    if not isinstance(data, dict):
        return {
            "shots": None,
            "sot": None
        }

    periods = data.get("periods")

    if periods is None:
        return {
            "shots": None,
            "sot": None
        }

    total_shots = 0
    shots_on_target = 0
    found_team = False

    for period in periods:

        for shot in period.get("shots") or []:

            if shot.get("team_id") != team_id:
                continue

            found_team = True
            total_shots += 1

            event_type = str(
                shot.get(
                    "event_type",
                    ""
                )
            ).strip().lower()

            # Chute no gol:
            # gol ou defesa do goleiro.
            if event_type in (
                "goal",
                "attemptsaved"
            ):
                shots_on_target += 1

    if not found_team:
        return {
            "shots": None,
            "sot": None
        }

    return {
        "shots": float(total_shots),
        "sot": float(shots_on_target)
    }


# =========================================================
# CARTÕES
# =========================================================

def get_cards(match_id, team_id):
    try:
        data = api_get(
            f"v1/matches/{match_id}/events"
        )

    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    events = data.get("events")

    if events is None:
        return None

    total = 0

    for event in events:

        if event.get("team_id") != team_id:
            continue

        event_type = str(
            event.get(
                "event_type",
                ""
            )
        ).strip().lower()

        if event_type in (
            "yellowcard",
            "redcard"
        ):
            total += 1

    return float(total)


# =========================================================
# JOGOS RECENTES
# =========================================================

def recent_matches(
    league_id,
    team_id,
    current_id,
    limit
):
    try:
        data = api_get(
            f"v1/leagues/{league_id}/matches"
        )

    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    matches = data.get("matches") or []

    result = []

    for match in matches:

        if match.get("id") == current_id:
            continue

        home = match.get("home_team") or {}
        away = match.get("away_team") or {}

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

        result.append(match)

    result.sort(
        key=lambda x: (
            x.get("time_utc")
            or x.get("date")
            or ""
        ),
        reverse=True
    )

    return result[:limit]


# =========================================================
# DADOS DE UM TIME EM UM JOGO
# =========================================================

def team_match_values(match, team_id):
    match_id = match.get("id")

    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    home_side = (
        home.get("id") == team_id
    )

    if home_side:
        goals = number(
            match.get("score_home")
        )
    else:
        goals = number(
            match.get("score_away")
        )

    stats = get_stats(
        match_id
    )

    corners = exact_stat(
        stats,
        [
            "corners",
            "corner_kicks"
        ],
        home_side
    )

    fouls = exact_stat(
        stats,
        [
            "fouls",
            "fouls_committed"
        ],
        home_side
    )

    shot_data = get_shots(
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
        "shots": shot_data["shots"],
        "sot": shot_data["sot"],
        "cards": cards,
        "fouls": fouls
    }


# =========================================================
# MÉDIAS
# =========================================================

def team_average(
    league_id,
    team_id,
    current_id,
    limit
):
    matches = recent_matches(
        league_id,
        team_id,
        current_id,
        limit
    )

    values = {
        "goals": [],
        "corners": [],
        "shots": [],
        "sot": [],
        "cards": [],
        "fouls": []
    }

    for match in matches:

        row = team_match_values(
            match,
            team_id
        )

        for key in values:
            values[key].append(
                row.get(key)
            )

    averages = {
        key: average(value)
        for key, value
        in values.items()
    }

    coverage = {
        key: len([
            x
            for x in value
            if x is not None
        ])
        for key, value
        in values.items()
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
        "timezone": TIMEZONE
    })


# =========================================================
# JOGOS DE HOJE
# =========================================================

@app.get("/api/fixtures/today")
def fixtures_today():
    try:
        today = datetime.now(
            ZoneInfo(TIMEZONE)
        ).strftime("%Y-%m-%d")

        data = api_get(
            f"v1/date/{today}"
        )

        matches = []

        if isinstance(data, dict):
            matches = (
                data.get("matches")
                or []
            )

        fixtures = [
            normalize_match(match)
            for match in matches
        ]

        return jsonify({
            "mode": "live",
            "message": "",
            "fixtures": fixtures
        })

    except Exception as error:

        return jsonify({
            "mode": "error",
            "message": str(error),
            "fixtures": []
        }), 502


# =========================================================
# ANÁLISE
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

        league_id = league.get("id")
        home_id = home.get("id")
        away_id = away.get("id")

        home_data = team_average(
            league_id,
            home_id,
            fixture_id,
            sample
        )

        away_data = team_average(
            league_id,
            away_id,
            fixture_id,
            sample
        )

        h = home_data["averages"]
        a = away_data["averages"]

        stats = [
            {
                "key": "goals",
                "label": "Gols",
                "home": h["goals"],
                "away": a["goals"]
            },
            {
                "key": "corners",
                "label": "Escanteios",
                "home": h["corners"],
                "away": a["corners"]
            },
            {
                "key": "shots",
                "label": "Finalizações",
                "home": h["shots"],
                "away": a["shots"]
            },
            {
                "key": "sot",
                "label": "Chutes no gol",
                "home": h["sot"],
                "away": a["sot"]
            },
            {
                "key": "cards",
                "label": "Cartões",
                "home": h["cards"],
                "away": a["cards"]
            },
            {
                "key": "fouls",
                "label": "Faltas",
                "home": h["fouls"],
                "away": a["fouls"]
            }
        ]

        return jsonify({
            "source": "PITCHAPI",
            "sample_size": sample,

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
                "id": away_id,
                "name": away.get(
                    "name",
                    "Visitante"
                ),
                "logo": away.get(
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

            "stats": stats
        })

    except Exception as error:

        return jsonify({
            "source": "PITCHAPI",
            "sample_size": sample,
            "stats": [],
            "error": str(error)
        }), 502


# =========================================================
# DEBUG DOS CHUTES
# =========================================================

@app.get("/api/debug/shots/<fixture_id>")
def debug_shots(fixture_id):

    try:
        data = api_get(
            f"v1/matches/{fixture_id}/shots"
        )

        return jsonify({
            "ok": True,
            "data": data
        })

    except Exception as error:

        return jsonify({
            "ok": False,
            "error": str(error)
        }), 502


# =========================================================
# LINHAS
# =========================================================

@app.get("/api/lines/<fixture_id>")
def lines(fixture_id):

    return jsonify({
        "message":
            "Aguardando validação das estatísticas.",
        "lines": []
    })


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
