from flask import Flask, jsonify, request, send_from_directory
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__, static_folder="static")

# =========================
# CONFIGURAÇÃO
# =========================

API_KEY = os.getenv("PITCHAPI_KEY", "").strip()
API_BASE = "https://api.pitchapi.dev"

TZ_NAME = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


# =========================
# PITCH API
# =========================

def api_headers():
    return {
        "X-API-KEY": API_KEY
    }


def api_get(path):
    if not API_KEY:
        raise RuntimeError("PITCHAPI_KEY não configurada no Render.")

    url = f"{API_BASE}/{path.lstrip('/')}"

    response = requests.get(
        url,
        headers=api_headers(),
        timeout=25
    )

    try:
        body = response.json()
    except Exception:
        raise RuntimeError(
            f"A PitchAPI retornou uma resposta inválida. "
            f"Status HTTP: {response.status_code}"
        )

    if not response.ok:
        error = body.get("error", {})

        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
        else:
            message = str(error)

        raise RuntimeError(
            message or f"Erro HTTP {response.status_code}"
        )

    return body.get("data")


# =========================
# FUNÇÕES AUXILIARES
# =========================

def local_time_from_utc(value):
    if not value:
        return ""

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        local = parsed.astimezone(
            ZoneInfo(TZ_NAME)
        )

        return local.strftime("%H:%M")

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

        "league_logo": "",

        "time": local_time_from_utc(
            item.get("time_utc")
        ),

        "status": item.get("status", ""),

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


# =========================
# SITE
# =========================

@app.get("/")
def index():
    return send_from_directory(
        "static",
        "index.html"
    )


# =========================
# TESTE DA API
# =========================

@app.get("/api/test-pitch")
def test_pitch():

    if not API_KEY:
        return jsonify({
            "ok": False,
            "error": "PITCHAPI_KEY não encontrada no Render."
        }), 500

    try:
        today = datetime.now(
            ZoneInfo(TZ_NAME)
        ).strftime("%Y-%m-%d")

        data = api_get(
            f"v1/date/{today}"
        )

        matches = []

        if isinstance(data, dict):
            matches = data.get(
                "matches",
                []
            )

        return jsonify({
            "ok": True,
            "provider": "PITCHAPI",
            "date": today,
            "matches_found": len(matches),
            "sample": matches[:3]
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 502


# =========================
# HEALTH
# =========================

@app.get("/api/health")
def health():

    return jsonify({
        "ok": True,
        "provider": "PITCHAPI",
        "api_configured": bool(API_KEY),
        "demo_mode": DEMO_MODE,
        "timezone": TZ_NAME
    })


# =========================
# JOGOS DE HOJE
# =========================

@app.get("/api/fixtures/today")
def fixtures_today():

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
        ).strftime("%Y-%m-%d")

        data = api_get(
            f"v1/date/{today}"
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

        return jsonify({
            "mode": "live",
            "message": "",
            "fixtures": fixtures
        })

    except Exception as e:

        return jsonify({
            "mode": "error",
            "message": str(e),
            "fixtures": []
        }), 502


# =========================
# DETALHES DA PARTIDA
# =========================

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


# =========================
# ESTATÍSTICAS DA PARTIDA
# =========================

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


# =========================
# CHUTES DA PARTIDA
# =========================

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


# =========================
# EVENTOS DA PARTIDA
# =========================

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


# =========================
# ANÁLISE
# =========================

@app.get("/api/analysis/<fixture_id>")
def analysis(fixture_id):

    sample = request.args.get(
        "sample",
        "10"
    )

    try:
        sample = 5 if int(sample) == 5 else 10
    except Exception:
        sample = 10

    # Por enquanto não vamos inventar médias.
    # Primeiro vamos validar os dados reais da PitchAPI.

    return jsonify({
        "source": "PITCHAPI",
        "sample_size": sample,
        "stats": [],
        "message":
            "PitchAPI conectada. "
            "Agora vamos validar as estatísticas reais "
            "antes de calcular as médias."
    })


# =========================
# LINHAS DE APOSTA
# =========================

@app.get("/api/lines/<fixture_id>")
def lines(fixture_id):

    return jsonify({
        "message":
            "As linhas automáticas serão liberadas "
            "depois da validação das estatísticas reais.",
        "lines": []
    })


# =========================
# INICIAR SERVIDOR
# =========================

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
