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
        raise RuntimeError("PITCHAPI_KEY não configurada.")

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
        raise RuntimeError(str(body))

    if isinstance(body, dict) and "data" in body:
        return body["data"]

    return body


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
    valid = [float(v) for v in values if v is not None]

    if not valid:
        return None

    return round(sum(valid) / len(valid), 2)


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
# JOGO
# =========================================================

def normalize_match(match):
    league = match.get("league") or {}
    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    return {
        "id": match.get("id"),
        "league": league.get("name", "Competição"),
        "league_id": league.get("id"),
        "league_logo": league.get("image_url", ""),
        "time": match_time(match.get("time_utc")),
        "status": match.get("status", ""),

        "home": {
            "id": home.get("id"),
            "name": home.get("name", "Mandante"),
            "logo": home.get("image_url", "")
        },

        "away": {
            "id": away.get("id"),
            "name": away.get("name", "Visitante"),
            "logo": away.get("image_url", "")
        },

        "demo": False
    }


# =========================================================
# ESTATÍSTICAS OFICIAIS
# =========================================================

def get_stats(match_id):
    try:
        data = api_get(
            f"v1/matches/{match_id}/stats"
        )
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    result = []

    for period in data.get("periods") or []:

        period_name = str(
            period.get("period", "")
        ).strip().lower()

        if period_name != "all":
            continue

        for group in period.get("groups") or []:

            for item in group.get("items") or []:

                result.append({
                    "key": str(
                        item.get("key", "")
                    ).strip().lower(),

                    "title": str(
                        item.get("title", "")
                    ).strip().lower(),

                    "home": number(item.get("home")),
                    "away": number(item.get("away"))
                })

    return result


def normalize_name(value):
    return (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def find_exact_stat(stats, names, home_side):
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

        if key in wanted or title in wanted:

            if home_side:
                return item.get("home")

            return item.get("away")

    return None


# =========================================================
# FINALIZAÇÕES
# =========================================================

def shot_events(match_id, team_id):
    try:
        data = api_get(
            f"v1/matches/{match_id}/shots"
        )
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    periods = data.get("periods")

    if periods is None:
        return None

    total = 0
    found = False

    for period in periods:

        for shot in period.get("shots") or []:

            if shot.get("team_id") != team_id:
                continue

            found = True
            total += 1

    if not found:
        return None

    return float(total)


# =========================================================
# CHUTES NO GOL - FALLBACK
# =========================================================

def sot_from_shots(match_id, team_id):
    try:
        data = api_get(
            f"v1/matches/{match_id}/shots"
        )
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    periods = data.get("periods")

    if periods is None:
        return None

    total = 0
    found = False

    for period in periods:

        for shot in period.get("shots") or []:

            if shot.get("team_id") != team_id:
                continue

            found = True

            event_type = (
                str(shot.get("event_type", ""))
                .strip()
                .lower()
                .replace("_", "")
                .replace(" ", "")
                .replace("-", "")
            )

            # Somente gol e defesa do goleiro
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

        event_type = (
            str(event.get("event_type", ""))
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

    result = []

    for match in data.get("matches") or []:

        if match.get("id") == current_id:
            continue

        home = match.get("home_team") or {}
        away = match.get("away_team") or {}

        if (
            home.get("id") != team_id
            and away.get("id") != team_id
        ):
            continue

        status = (
            str(match.get("status", ""))
            .strip()
            .lower()
        )

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
# ESTATÍSTICAS DE UM TIME
# =========================================================

def team_match_values(match, team_id):
    match_id = match.get("id")

    home = match.get("home_team") or {}

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

    stats = get_stats(match_id)

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

    # ---------------------------------------------
    # FINALIZAÇÕES
    # ---------------------------------------------

    shots = find_exact_stat(
        stats,
        [
            "shots",
            "total_shots",
            "total shots"
        ],
        home_side
    )

    # Se não existir em /stats, conta /shots.
    if shots is None:
        shots = shot_events(
            match_id,
            team_id
        )

    # ---------------------------------------------
    # CHUTES NO GOL
    # ---------------------------------------------

    # PRIORIDADE:
    # estatística oficial do jogo.
    sot = find_exact_stat(
        stats,
        [
            "shots_on_target",
            "shots on target"
        ],
        home_side
    )

    # Só usa os eventos se a estatística oficial
    # realmente não estiver disponível.
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

    return {
        "matches_used": len(matches),

        "averages": {
            key: average(value)
            for key, value in values.items()
        },

        "coverage": {
            key: len([
                x
                for x in value
                if x is not None
            ])
            for key, value in values.items()
        }
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
        "api_configured": bool(API_KEY),
        "demo_mode": False,
        "timezone": TIMEZONE,
        "version": "SOT-FIX-2"
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
            matches = data.get("matches") or []

        return jsonify({
            "mode": "live",
            "message": "",
            "fixtures": [
                normalize_match(match)
                for match in matches
            ]
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
            request.args.get("sample", 10)
        )
    except Exception:
        sample = 10

    if sample not in (5, 10):
        sample = 10

    try:
        fixture = api_get(
            f"v1/matches/{fixture_id}"
        )

        if not isinstance(fixture, dict):
            raise RuntimeError(
                "Partida não encontrada."
            )

        league = fixture.get("league") or {}
        home = fixture.get("home_team") or {}
        away = fixture.get("away_team") or {}

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

        return jsonify({
            "source": "PITCHAPI",
            "version": "SOT-FIX-2",
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
                    home_data["matches_used"],
                "coverage":
                    home_data["coverage"]
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
                    away_data["matches_used"],
                "coverage":
                    away_data["coverage"]
            },

            "stats": [
                {
                    "label": "Gols",
                    "home": h["goals"],
                    "away": a["goals"]
                },
                {
                    "label": "Escanteios",
                    "home": h["corners"],
                    "away": a["corners"]
                },
                {
                    "label": "Finalizações",
                    "home": h["shots"],
                    "away": a["shots"]
                },
                {
                    "label": "Chutes no gol",
                    "home": h["sot"],
                    "away": a["sot"]
                },
                {
                    "label": "Cartões",
                    "home": h["cards"],
                    "away": a["cards"]
                },
                {
                    "label": "Faltas",
                    "home": h["fouls"],
                    "away": a["fouls"]
                }
            ]
        })

    except Exception as error:

        return jsonify({
            "source": "PITCHAPI",
            "version": "SOT-FIX-2",
            "sample_size": sample,
            "stats": [],
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
        os.getenv("PORT", "5000")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
