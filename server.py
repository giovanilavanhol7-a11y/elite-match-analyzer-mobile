from flask import Flask, jsonify, request, send_from_directory
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__, static_folder="static")

API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
API_BASE = os.getenv("API_FOOTBALL_BASE", "https://v3.football.api-sports.io").rstrip("/")
TZ_NAME = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

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
    },
    {
        "id": 1002,
        "league": "Premier League",
        "league_logo": "",
        "time": "18:30",
        "status": "NS",
        "home": {"id": 3, "name": "Manchester City", "logo": ""},
        "away": {"id": 4, "name": "Liverpool", "logo": ""},
        "demo": True,
    },
]

DEMO_ANALYSIS = {
    1001: {
        "source": "DEMO",
        "sample_size": 10,
        "home": "Flamengo",
        "away": "Palmeiras",
        "stats": [
            {"key": "goals", "label": "Gols", "home": 1.8, "away": 1.5},
            {"key": "corners", "label": "Escanteios", "home": 6.1, "away": 5.4},
            {"key": "shots", "label": "Finalizações", "home": 15.2, "away": 13.7},
            {"key": "sot", "label": "Chutes no gol", "home": 5.8, "away": 4.9},
            {"key": "cards", "label": "Cartões", "home": 2.4, "away": 2.8},
            {"key": "fouls", "label": "Faltas", "home": 12.3, "away": 14.1},
        ],
    },
    1002: {
        "source": "DEMO",
        "sample_size": 10,
        "home": "Manchester City",
        "away": "Liverpool",
        "stats": [
            {"key": "goals", "label": "Gols", "home": 2.2, "away": 2.0},
            {"key": "corners", "label": "Escanteios", "home": 7.0, "away": 6.3},
            {"key": "shots", "label": "Finalizações", "home": 17.1, "away": 16.2},
            {"key": "sot", "label": "Chutes no gol", "home": 6.6, "away": 6.1},
            {"key": "cards", "label": "Cartões", "home": 1.7, "away": 2.1},
            {"key": "fouls", "label": "Faltas", "home": 9.8, "away": 10.7},
        ],
    },
}

def api_headers():
    return {"x-apisports-key": API_KEY}

def api_get(path, params=None):
    if not API_KEY:
        raise RuntimeError("API_FOOTBALL_KEY não configurada")
    r = requests.get(f"{API_BASE}/{path.lstrip('/')}", headers=api_headers(), params=params or {}, timeout=20)
    r.raise_for_status()
    body = r.json()
    errors = body.get("errors")
    if errors:
        raise RuntimeError(str(errors))
    return body.get("response", [])

def normalize_fixture(item):
    fixture = item.get("fixture", {})
    league = item.get("league", {})
    teams = item.get("teams", {})
    dt = fixture.get("date", "")
    local_time = ""
    try:
        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(ZoneInfo(TZ_NAME))
        local_time = parsed.strftime("%H:%M")
    except Exception:
        local_time = dt[11:16] if len(dt) >= 16 else ""
    return {
        "id": fixture.get("id"),
        "league": league.get("name", "Competição"),
        "league_logo": league.get("logo", ""),
        "time": local_time,
        "status": (fixture.get("status") or {}).get("short", ""),
        "home": {
            "id": (teams.get("home") or {}).get("id"),
            "name": (teams.get("home") or {}).get("name", "Mandante"),
            "logo": (teams.get("home") or {}).get("logo", ""),
        },
        "away": {
            "id": (teams.get("away") or {}).get("id"),
            "name": (teams.get("away") or {}).get("name", "Visitante"),
            "logo": (teams.get("away") or {}).get("logo", ""),
        },
        "demo": False,
    }

def stat_value(stats, stat_type):
    for s in stats or []:
        if s.get("type") == stat_type:
            value = s.get("value")
            if value is None:
                return 0.0
            if isinstance(value, str) and value.endswith("%"):
                value = value[:-1]
            try:
                return float(value)
            except Exception:
                return 0.0
    return 0.0

def fetch_team_recent_fixture_ids(team_id, before_date, count=10):
    season = datetime.now(ZoneInfo(TZ_NAME)).year
    rows = api_get("fixtures", {
        "team": team_id,
        "last": count,
        "season": season,
        "status": "FT"
    })
    return [r.get("fixture", {}).get("id") for r in rows if r.get("fixture", {}).get("id")]

def fetch_average_stats(team_id, fixture_ids):
    totals = {"corners":0.0,"shots":0.0,"sot":0.0,"cards":0.0,"fouls":0.0,"goals":0.0}
    used = 0
    for fixture_id in fixture_ids[:10]:
        try:
            stats_response = api_get("fixtures/statistics", {"fixture": fixture_id})
            fixture_detail = api_get("fixtures", {"id": fixture_id})
            if not fixture_detail:
                continue
            fixture_item = fixture_detail[0]
            goals = fixture_item.get("goals") or {}
            teams = fixture_item.get("teams") or {}
            is_home = (teams.get("home") or {}).get("id") == team_id
            team_stats = None
            for row in stats_response:
                if (row.get("team") or {}).get("id") == team_id:
                    team_stats = row.get("statistics") or []
                    break
            if team_stats is None:
                continue
            totals["goals"] += float(goals.get("home" if is_home else "away") or 0)
            totals["corners"] += stat_value(team_stats, "Corner Kicks")
            totals["shots"] += stat_value(team_stats, "Total Shots")
            totals["sot"] += stat_value(team_stats, "Shots on Goal")
            totals["fouls"] += stat_value(team_stats, "Fouls")
            yellow = stat_value(team_stats, "Yellow Cards")
            red = stat_value(team_stats, "Red Cards")
            totals["cards"] += yellow + red
            used += 1
        except Exception:
            continue
    if used == 0:
        return None, 0
    return {k: round(v/used, 2) for k,v in totals.items()}, used

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "api_configured": bool(API_KEY),
        "demo_mode": DEMO_MODE,
        "timezone": TZ_NAME,
    })

@app.get("/api/fixtures/today")
def fixtures_today():
    if DEMO_MODE or not API_KEY:
        return jsonify({
            "mode": "demo",
            "message": "Modo demonstração: configure API_FOOTBALL_KEY para usar partidas reais.",
            "fixtures": DEMO_FIXTURES,
        })
    try:
        today = datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d")
        rows = api_get("fixtures", {"date": today, "timezone": TZ_NAME})
        fixtures = [normalize_fixture(x) for x in rows]
        return jsonify({"mode": "live", "message": "", "fixtures": fixtures})
    except Exception as e:
        return jsonify({"mode": "error", "message": str(e), "fixtures": []}), 502

@app.get("/api/analysis/<int:fixture_id>")
def analysis(fixture_id):
    sample = request.args.get("sample", "10")
    try:
        sample = 5 if int(sample) == 5 else 10
    except Exception:
        sample = 10

    if DEMO_MODE or not API_KEY:
        demo = DEMO_ANALYSIS.get(fixture_id)
        if not demo:
            return jsonify({"error": "Partida de demonstração não encontrada."}), 404
        response = dict(demo)
        response["sample_size"] = sample
        return jsonify(response)

    try:
        rows = api_get("fixtures", {"id": fixture_id})
        if not rows:
            return jsonify({"error": "Partida não encontrada."}), 404
        item = rows[0]
        teams = item.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}

        home_ids = fetch_team_recent_fixture_ids(home.get("id"), None, sample)
        away_ids = fetch_team_recent_fixture_ids(away.get("id"), None, sample)

        home_avg, home_used = fetch_average_stats(home.get("id"), home_ids)
        away_avg, away_used = fetch_average_stats(away.get("id"), away_ids)

        if not home_avg or not away_avg:
            return jsonify({"error": "Não foi possível calcular estatísticas suficientes para esta partida."}), 422

        order = [
            ("goals","Gols"),
            ("corners","Escanteios"),
            ("shots","Finalizações"),
            ("sot","Chutes no gol"),
            ("cards","Cartões"),
            ("fouls","Faltas"),
        ]
        stats = [
            {"key":k, "label":label, "home":home_avg[k], "away":away_avg[k]}
            for k,label in order
        ]

        return jsonify({
            "source": "API-FOOTBALL",
            "sample_size": min(home_used, away_used),
            "home": home.get("name"),
            "away": away.get("name"),
            "stats": stats,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/lines/<int:fixture_id>")
def lines(fixture_id):
    return jsonify({
        "message": "As linhas automáticas serão habilitadas somente depois que validarmos os dados reais da partida.",
        "lines": []
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
