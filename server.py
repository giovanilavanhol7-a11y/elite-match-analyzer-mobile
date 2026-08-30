from flask import Flask, jsonify, request, send_from_directory
import os
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

app = Flask(__name__, static_folder="static")

API_KEY = os.getenv("SPORTMONKS_TOKEN", "").strip()
API_BASE = "https://api.sportmonks.com/v3/football"

TZ_NAME = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


DEMO_FIXTURES = [
    {
        "id": 1001,
        "league": "Brasileirão Série A",
        "league_logo": "",
        "time": "16:00",
        "status": "NS",
        "home": {"id": 1, "name": "Flamengo", "logo": ""},
        "away": {"id": 2, "name": "Palmeiras", "logo": ""},
        "demo": True,
    }
]


def api_get(path, params=None):
    if not API_KEY:
        raise RuntimeError("SPORTMONKS_TOKEN não configurado")

    query = dict(params or {})
    query["api_token"] = API_KEY

    url = f"{API_BASE}/{path.lstrip('/')}"

    response = requests.get(url, params=query, timeout=25)

    try:
        body = response.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida da Sportmonks ({response.status_code})"
        )

    if not response.ok:
        message = (
            body.get("message")
            or body.get("error")
            or str(body)
        )
        raise RuntimeError(f"Sportmonks: {message}")

    return body.get("data")


def api_get_list(path, params=None):
    data = api_get(path, params)

    if data is None:
        return []

    if isinstance(data, list):
        return data

    return [data]


def local_fixture_time(starting_at):
    if not starting_at:
        return ""

    try:
        text = str(starting_at).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        dt = dt.astimezone(ZoneInfo(TZ_NAME))
        return dt.strftime("%H:%M")

    except Exception:
        text = str(starting_at)
        return text[11:16] if len(text) >= 16 else ""


def get_home_away(participants):
    home = None
    away = None

    for team in participants or []:
        meta = team.get("meta") or {}
        location = str(meta.get("location", "")).lower()

        if location == "home":
            home = team
        elif location == "away":
            away = team

    if not home and participants:
        home = participants[0]

    if not away and participants and len(participants) > 1:
        away = participants[1]

    return home or {}, away or {}


def normalize_fixture(item):
    participants = item.get("participants") or []
    home, away = get_home_away(participants)

    league = item.get("league") or {}
    state = item.get("state") or {}

    status = (
        state.get("short_name")
        or state.get("developer_name")
        or state.get("name")
        or str(item.get("state_id", ""))
    )

    return {
        "id": item.get("id"),
        "league": league.get("name", "Competição"),
        "league_logo": league.get("image_path", ""),
        "time": local_fixture_time(item.get("starting_at")),
        "status": status,
        "home": {
            "id": home.get("id"),
            "name": home.get("name", "Mandante"),
            "logo": home.get("image_path", ""),
        },
        "away": {
            "id": away.get("id"),
            "name": away.get("name", "Visitante"),
            "logo": away.get("image_path", ""),
        },
        "demo": False,
    }


def numeric_value(value):
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value.replace("%", "").strip())
        except Exception:
            return 0.0

    if isinstance(value, dict):
        for key in ["total", "count", "value", "goals"]:
            if key in value:
                try:
                    return float(value[key] or 0)
                except Exception:
                    pass

    return 0.0


def fixture_stat(fixture, team_id, developer_names, type_ids=None):
    wanted_names = {str(x).upper() for x in developer_names}
    wanted_ids = set(type_ids or [])

    for stat in fixture.get("statistics") or []:
        if stat.get("participant_id") != team_id:
            continue

        type_id = stat.get("type_id")
        type_info = stat.get("type") or {}

        developer_name = str(
            type_info.get("developer_name", "")
        ).upper()

        code = str(
            type_info.get("code", "")
        ).upper().replace("-", "_")

        if (
            type_id in wanted_ids
            or developer_name in wanted_names
            or code in wanted_names
        ):
            data = stat.get("data")

            if isinstance(data, dict):
                if "value" in data:
                    data = data.get("value")

            return numeric_value(data)

    return 0.0


def goals_for_team(fixture, team_id):
    goals = []

    for score in fixture.get("scores") or []:
        if score.get("participant_id") != team_id:
            continue

        score_data = score.get("score") or {}
        value = score_data.get("goals")

        if value is not None:
            try:
                goals.append(float(value))
            except Exception:
                pass

    return max(goals) if goals else 0.0


def fetch_team_recent_fixtures(team_id, count=10):
    tz = ZoneInfo(TZ_NAME)

    end_date = (
        datetime.now(tz) - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    start_date = (
        datetime.now(tz) - timedelta(days=365)
    ).strftime("%Y-%m-%d")

    path = (
        f"fixtures/between/"
        f"{start_date}/"
        f"{end_date}/"
        f"{team_id}"
    )

    rows = api_get_list(
        path,
        {
            "include": (
                "participants;"
                "statistics.type;"
                "scores;"
                "state"
            ),
            "order": "desc",
            "per_page": 50,
        }
    )

    return rows[:count]


def fetch_average_stats(team_id, fixtures):
    totals = {
        "goals": 0.0,
        "corners": 0.0,
        "shots": 0.0,
        "sot": 0.0,
        "cards": 0.0,
        "fouls": 0.0,
    }

    used = 0

    for fixture in fixtures:
        try:
            totals["goals"] += goals_for_team(fixture, team_id)

            totals["corners"] += fixture_stat(
                fixture,
                team_id,
                ["CORNERS", "CORNER_KICKS", "CORNERS_TOTAL"]
            )

            totals["shots"] += fixture_stat(
                fixture,
                team_id,
                ["SHOTS_TOTAL", "TOTAL_SHOTS", "SHOTS", "GOAL_ATTEMPTS"],
                [42]
            )

            totals["sot"] += fixture_stat(
                fixture,
                team_id,
                ["SHOTS_ON_TARGET", "SHOTS_ONTARGET", "ON_TARGET"],
                [86]
            )

            totals["fouls"] += fixture_stat(
                fixture,
                team_id,
                ["FOULS", "FOULS_COMMITTED"],
                [56]
            )

            yellow = fixture_stat(
                fixture,
                team_id,
                ["YELLOWCARDS", "YELLOW_CARDS"]
            )

            red = fixture_stat(
                fixture,
                team_id,
                ["REDCARDS", "RED_CARDS"]
            )

            totals["cards"] += yellow + red
            used += 1

        except Exception:
            continue

    if used == 0:
        return None, 0

    return {
        key: round(value / used, 2)
        for key, value in totals.items()
    }, used


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "provider": "Sportmonks",
        "api_configured": bool(API_KEY),
        "demo_mode": DEMO_MODE,
        "timezone": TZ_NAME,
    })


@app.get("/api/fixtures/today")
def fixtures_today():
    if DEMO_MODE or not API_KEY:
        return jsonify({
            "mode": "demo",
            "message": "Configure SPORTMONKS_TOKEN para usar partidas reais.",
            "fixtures": DEMO_FIXTURES,
        })

    try:
        today = datetime.now(
            ZoneInfo(TZ_NAME)
        ).strftime("%Y-%m-%d")

        rows = api_get_list(
            f"fixtures/date/{today}",
            {
                "include": "participants;league;state",
                "per_page": 50,
            }
        )

        fixtures = [normalize_fixture(row) for row in rows]

        return jsonify({
            "mode": "live",
            "message": "",
            "fixtures": fixtures,
        })

    except Exception as e:
        return jsonify({
            "mode": "error",
            "message": str(e),
            "fixtures": [],
        }), 502


@app.get("/api/analysis/<int:fixture_id>")
def analysis(fixture_id):
    sample = request.args.get("sample", "10")

    try:
        sample = 5 if int(sample) == 5 else 10
    except Exception:
        sample = 10

    try:
        item = api_get(
            f"fixtures/{fixture_id}",
            {"include": "participants;league;state"}
        )

        if not item:
            return jsonify({"error": "Partida não encontrada."}), 404

        participants = item.get("participants") or []
        home, away = get_home_away(participants)

        home_id = home.get("id")
        away_id = away.get("id")

        home_fixtures = fetch_team_recent_fixtures(home_id, sample)
        away_fixtures = fetch_team_recent_fixtures(away_id, sample)

        home_avg, home_used = fetch_average_stats(
            home_id,
            home_fixtures
        )

        away_avg, away_used = fetch_average_stats(
            away_id,
            away_fixtures
        )

        order = [
            ("goals", "Gols"),
            ("corners", "Escanteios"),
            ("shots", "Finalizações"),
            ("sot", "Chutes no gol"),
            ("cards", "Cartões"),
            ("fouls", "Faltas"),
        ]

        stats = [
            {
                "key": key,
                "label": label,
                "home": home_avg[key],
                "away": away_avg[key],
            }
            for key, label in order
        ]

        return jsonify({
            "source": "SPORTMONKS",
            "sample_size": min(home_used, away_used),
            "home": home.get("name", "Mandante"),
            "away": away.get("name", "Visitante"),
            "stats": stats,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.get("/api/debug/team/<int:team_id>")
def debug_team(team_id):
    try:
        fixtures = fetch_team_recent_fixtures(team_id, 3)

        result = []

        for fixture in fixtures:
            stats_output = []

            for stat in fixture.get("statistics") or []:
                if stat.get("participant_id") != team_id:
                    continue

                type_info = stat.get("type") or {}

                stats_output.append({
                    "type_id": stat.get("type_id"),
                    "developer_name": type_info.get("developer_name"),
                    "code": type_info.get("code"),
                    "name": type_info.get("name"),
                    "data": stat.get("data"),
                    "value": stat.get("value"),
                })

            result.append({
                "fixture_id": fixture.get("id"),
                "starting_at": fixture.get("starting_at"),
                "statistics": stats_output,
            })

        return jsonify({
            "team_id": team_id,
            "fixtures": result,
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 502


@app.get("/api/lines/<int:fixture_id>")
def lines(fixture_id):
    return jsonify({
        "message": "Linhas automáticas ainda em validação.",
        "lines": []
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
