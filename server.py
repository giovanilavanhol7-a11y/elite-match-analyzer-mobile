from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import os
import time
import requests
import re
import unicodedata
from difflib import SequenceMatcher


app = Flask(__name__, static_folder="static")

API_KEY = os.getenv("PITCHAPI_KEY", "").strip()
API_BASE = "https://api.pitchapi.dev"
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "").strip()
FOOTBALL_DATA_BASE = "https://api.5dollarfootballapi.com/v1"

FOOTBALL_DATA_CACHE = {}
FOOTBALL_DATA_CACHE_SECONDS = 900
TIMEZONE = "America/Sao_Paulo"

FIXTURES_CACHE = {
    "date": None,
    "created_at": 0,
    "matches": []
}
FIXTURES_CACHE_SECONDS = 300

LEAGUES_CACHE = {
    "created_at": 0,
    "leagues": []
}
LEAGUES_CACHE_SECONDS = 3600

LEAGUE_MATCHES_CACHE = {}
LEAGUE_MATCHES_CACHE_SECONDS = 1800

MATCH_DATA_CACHE = {}
MATCH_DATA_CACHE_SECONDS = 1800


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


def api_get_cached(path, ttl=MATCH_DATA_CACHE_SECONDS):
    now = time.time()
    cached = MATCH_DATA_CACHE.get(path)

    if (
        cached
        and (
            now - cached["created_at"] < ttl
        )
    ):
        return cached["data"]

    data = api_get(path)

    MATCH_DATA_CACHE[path] = {
        "created_at": now,
        "data": data
    }

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


def parse_utc(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except Exception:
        return None


def match_time(value):
    dt = parse_utc(value)

    if dt is None:
        return ""

    try:
        return dt.astimezone(
            ZoneInfo(TIMEZONE)
        ).strftime("%H:%M")
    except Exception:
        return ""


def match_date(value):
    dt = parse_utc(value)

    if dt is None:
        return ""

    try:
        return dt.astimezone(
            ZoneInfo(TIMEZONE)
        ).strftime("%d/%m/%Y")
    except Exception:
        return ""


def local_match_day(value):
    dt = parse_utc(value)

    if dt is None:
        return None

    try:
        return dt.astimezone(
            ZoneInfo(TIMEZONE)
        ).strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_name(value):
    return (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


# =========================================================
# CONTEXTO DA PARTIDA
# =========================================================

def build_match_context(fixture):
    referee = clean_text(fixture.get("referee"))
    stadium = clean_text(fixture.get("stadium"))
    round_name = clean_text(fixture.get("round_name"))
    date = clean_text(fixture.get("date"))
    status = clean_text(fixture.get("status"))
    kickoff = match_time(fixture.get("time_utc"))

    return {
        "referee": referee or None,
        "stadium": stadium or None,
        "round": round_name or None,
        "date": date or None,
        "time": kickoff or None,
        "status": status or None
    }


# =========================================================
# H2H
# =========================================================

def empty_h2h():
    return {
        "available": False,
        "total_matches": 0,
        "home_wins": 0,
        "draws": 0,
        "away_wins": 0,
        "recent_matches": []
    }


def get_h2h(fixture_id):
    try:
        data = api_get(
            f"v1/matches/{fixture_id}/h2h"
        )
    except Exception:
        return empty_h2h()

    if not isinstance(data, dict):
        return empty_h2h()

    recent = []

    for match in data.get("recent_matches") or []:
        if not match.get("finished", False):
            continue

        home = (
            match.get("home")
            or match.get("home_team")
            or {}
        )

        away = (
            match.get("away")
            or match.get("away_team")
            or {}
        )

        score_home = number(match.get("score_home"))
        score_away = number(match.get("score_away"))

        if score_home is None or score_away is None:
            continue

        recent.append({
            "date": match_date(match.get("time_utc")),
            "time_utc": match.get("time_utc"),
            "home": {
                "id": home.get("id"),
                "name": home.get("name", "Mandante")
            },
            "away": {
                "id": away.get("id"),
                "name": away.get("name", "Visitante")
            },
            "score_home": int(score_home),
            "score_away": int(score_away),
            "finished": True
        })

    recent.sort(
        key=lambda item: item.get("time_utc") or "",
        reverse=True
    )

    home_team = data.get("home_team") or {}
    away_team = data.get("away_team") or {}

    return {
        "available": True,
        "home_team": {
            "id": home_team.get("id"),
            "name": home_team.get("name", "Mandante")
        },
        "away_team": {
            "id": away_team.get("id"),
            "name": away_team.get("name", "Visitante")
        },
        "total_matches": int(data.get("total_matches") or 0),
        "home_wins": int(data.get("home_wins") or 0),
        "draws": int(data.get("draws") or 0),
        "away_wins": int(data.get("away_wins") or 0),
        "recent_matches": recent[:10]
    }


# =========================================================
# NORMALIZAR PARTIDA
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
        data = api_get_cached(
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


def find_exact_stat(stats, names, home_side):
    wanted = {
        normalize_name(name)
        for name in names
    }

    for item in stats:
        key = normalize_name(item.get("key"))
        title = normalize_name(item.get("title"))

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
        data = api_get_cached(
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
# CHUTES NO GOL
# =========================================================

def sot_from_shots(match_id, team_id):
    try:
        data = api_get_cached(
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

def get_card_breakdown(match_id, team_id):
    try:
        data = api_get_cached(
            f"v1/matches/{match_id}/events"
        )
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    events = data.get("events")

    if events is None:
        return None

    yellow = 0
    red = 0

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

        if event_type == "yellowcard":
            yellow += 1
        elif event_type == "redcard":
            red += 1

    return {
        "yellow_cards": float(yellow),
        "red_cards": float(red),
        "cards": float(yellow + red)
    }


# =========================================================
# ÚLTIMOS JOGOS
# =========================================================

def _season_sort_key(value):
    text = str(value or "")
    years = re.findall(r"\d{4}", text)

    if not years:
        return (0, 0, text)

    nums = [int(year) for year in years]

    return (
        max(nums),
        min(nums),
        text
    )


def get_all_leagues_cached():
    now = time.time()

    if (
        LEAGUES_CACHE["leagues"]
        and (
            now
            - LEAGUES_CACHE["created_at"]
            < LEAGUES_CACHE_SECONDS
        )
    ):
        return LEAGUES_CACHE["leagues"]

    data = api_get("v1/leagues")
    leagues = extract_leagues(data)

    LEAGUES_CACHE["created_at"] = now
    LEAGUES_CACHE["leagues"] = leagues

    return leagues


def get_league_seasons(league_id):
    try:
        leagues = get_all_leagues_cached()
    except Exception:
        return []

    for league in leagues:
        if not isinstance(league, dict):
            continue

        if league.get("id") != league_id:
            continue

        seasons = league.get("seasons") or []

        if not isinstance(seasons, list):
            return []

        cleaned = []

        for season in seasons:
            if season is None:
                continue

            value = str(season).strip()

            if value and value not in cleaned:
                cleaned.append(value)

        cleaned.sort(
            key=_season_sort_key,
            reverse=True
        )

        return cleaned

    return []


def get_league_matches_cached( league_id, season=None ):
    cache_key = (
        league_id,
        str(season or "")
    )

    now = time.time()

    cached = LEAGUE_MATCHES_CACHE.get(
        cache_key
    )

    if (
        cached
        and (
            now
            - cached["created_at"]
            < LEAGUE_MATCHES_CACHE_SECONDS
        )
    ):
        return cached["matches"]

    if season:
        season_param = quote(
            str(season),
            safe=""
        )

        path = (
            f"v1/leagues/{league_id}/matches"
            f"?season={season_param}"
        )
    else:
        path = (
            f"v1/leagues/{league_id}/matches"
        )

    data = api_get(path)

    if not isinstance(data, dict):
        matches = []
    else:
        matches = data.get("matches") or []

    LEAGUE_MATCHES_CACHE[
        cache_key
    ] = {
        "created_at": now,
        "matches": matches
    }

    return matches


def _finished_match_status(match):
    status = str(
        match.get("status", "")
    ).strip().lower()

    return status in (
        "finished",
        "complete",
        "completed",
        "ft",
        "full_time",
        "full time"
    )


def _match_fits_team_venue( match, team_id, venue ):
    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    if venue == "home":
        return home.get("id") == team_id

    if venue == "away":
        return away.get("id") == team_id

    return (
        home.get("id") == team_id
        or away.get("id") == team_id
    )


def recent_matches( league_id, team_id, current_id, limit, venue ):
    if not league_id:
        return []

    # SOMENTE A TEMPORADA ATUAL.
    # O endpoint sem ?season= usa a temporada corrente da liga
    # na PitchAPI. Não buscamos temporada anterior.
    try:
        matches = get_league_matches_cached(
            league_id,
            None
        )
    except Exception:
        return []

    ordered = list(matches)

    ordered.sort(
        key=lambda item: (
            item.get("time_utc")
            or item.get("date")
            or ""
        ),
        reverse=True
    )

    result = []
    seen_ids = set()

    for match in ordered:
        match_id = match.get("id")

        if not match_id:
            continue

        if match_id == current_id:
            continue

        if match_id in seen_ids:
            continue

        if not _finished_match_status(match):
            continue

        if not _match_fits_team_venue(
            match,
            team_id,
            venue
        ):
            continue

        seen_ids.add(match_id)
        result.append(match)

        if len(result) >= limit:
            break

    return result[:limit]


# =========================================================
# DADOS DA EQUIPE EM UMA PARTIDA
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

    card_data = get_card_breakdown(
        match_id,
        team_id
    )

    if card_data is None:
        yellow_cards = None
        red_cards = None
        cards = None
    else:
        yellow_cards = card_data[
            "yellow_cards"
        ]
        red_cards = card_data[
            "red_cards"
        ]
        cards = card_data[
            "cards"
        ]

    return {
        "goals": goals,
        "corners": corners,
        "shots": shots,
        "sot": sot,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "cards": cards,
        "fouls": fouls
    }


# =========================================================
# ADVERSÁRIO
# =========================================================

def opponent_id_from_match(match, team_id):
    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    if home.get("id") == team_id:
        return away.get("id")

    if away.get("id") == team_id:
        return home.get("id")

    return None


# =========================================================
# MÉDIA
# =========================================================

def team_average( league_id, team_id, current_id, limit, venue ):
    matches = recent_matches(
        league_id,
        team_id,
        current_id,
        limit,
        venue
    )

    keys = [
        "goals",
        "corners",
        "shots",
        "sot",
        "yellow_cards",
        "red_cards",
        "cards",
        "fouls"
    ]

    produced = {
        key: []
        for key in keys
    }

    conceded = {
        key: []
        for key in keys
    }

    history = []

    def process_match(match):
        own_row = team_match_values(
            match,
            team_id
        )

        opponent_id = opponent_id_from_match(
            match,
            team_id
        )

        if opponent_id:
            conceded_row = team_match_values(
                match,
                opponent_id
            )
        else:
            conceded_row = {
                key: None
                for key in keys
            }

        home = match.get("home_team") or {}
        away = match.get("away_team") or {}

        return {
            "match_id": match.get("id"),
            "home": home.get("name", ""),
            "away": away.get("name", ""),
            "produced": own_row,
            "conceded": conceded_row
        }

    rows_by_id = {}

    # Bounded concurrency: enough to avoid Render timeout without
    # creating a large burst against PitchAPI.
    if matches:
        with ThreadPoolExecutor(
            max_workers=min(4, len(matches))
        ) as executor:
            future_map = {
                executor.submit(
                    process_match,
                    match
                ): match.get("id")
                for match in matches
            }

            for future in as_completed(
                future_map
            ):
                match_id = future_map[future]

                try:
                    rows_by_id[
                        match_id
                    ] = future.result()
                except Exception:
                    continue

    # Preserve chronological order from recent_matches.
    for match in matches:
        row = rows_by_id.get(
            match.get("id")
        )

        if not row:
            continue

        own_row = row["produced"]
        conceded_row = row["conceded"]

        for key in keys:
            produced[key].append(
                own_row.get(key)
            )
            conceded[key].append(
                conceded_row.get(key)
            )

        history.append(row)

    return {
        "matches_used": len(history),
        "venue": venue,
        "averages": {
            key: average(values)
            for key, values
            in produced.items()
        },
        "coverage": {
            key: len([
                value
                for value in values
                if value is not None
            ])
            for key, values
            in produced.items()
        },
        "values": produced,
        "conceded_averages": {
            key: average(values)
            for key, values
            in conceded.items()
        },
        "conceded_coverage": {
            key: len([
                value
                for value in values
                if value is not None
            ])
            for key, values
            in conceded.items()
        },
        "conceded_values": conceded,
        "history": history
    }


# =========================================================
# RECORTE 5 JOGOS
# =========================================================

def slice_team_data(team_data, limit):
    produced = {
        key: values[:limit]
        for key, values
        in team_data["values"].items()
    }

    conceded = {
        key: values[:limit]
        for key, values
        in team_data[
            "conceded_values"
        ].items()
    }

    history = team_data[
        "history"
    ][:limit]

    return {
        "matches_used": len(history),
        "venue": team_data.get("venue"),
        "averages": {
            key: average(values)
            for key, values
            in produced.items()
        },
        "coverage": {
            key: len([
                value
                for value in values
                if value is not None
            ])
            for key, values
            in produced.items()
        },
        "values": produced,
        "conceded_averages": {
            key: average(values)
            for key, values
            in conceded.items()
        },
        "conceded_coverage": {
            key: len([
                value
                for value in values
                if value is not None
            ])
            for key, values
            in conceded.items()
        },
        "conceded_values": conceded,
        "history": history
    }


# =========================================================
# LINHAS
# =========================================================

def line_result(values, threshold):
    valid = [
        float(value)
        for value in values
        if value is not None
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

    return {
        "line": threshold,
        "hits": hits,
        "games": len(valid),
        "rate": round(
            hits / len(valid) * 100,
            1
        )
    }


LINE_DEFINITIONS = [
    ("goals", "+0.5 Gols", 0.5),
    ("corners", "+3.5 Escanteios", 3.5),
    ("corners", "+4.5 Escanteios", 4.5),
    ("shots", "+9.5 Finalizações", 9.5),
    ("shots", "+12.5 Finalizações", 12.5),
    ("sot", "+2.5 Chutes no gol", 2.5),
    ("sot", "+3.5 Chutes no gol", 3.5),
    (
        "yellow_cards",
        "+0.5 Cartões amarelos",
        0.5
    ),
    (
        "yellow_cards",
        "+1.5 Cartões amarelos",
        1.5
    ),
    (
        "yellow_cards",
        "+2.5 Cartões amarelos",
        2.5
    ),
    (
        "red_cards",
        "+0.5 Cartões vermelhos",
        0.5
    ),
    ("fouls", "+9.5 Faltas", 9.5),
    ("fouls", "+10.5 Faltas", 10.5)
]


def build_lines_from_values(values):
    result = []

    for metric, label, threshold in LINE_DEFINITIONS:
        result.append({
            "metric": metric,
            "label": label,
            **line_result(
                values.get(metric, []),
                threshold
            )
        })

    return result


def build_lines(team_data):
    return build_lines_from_values(
        team_data["values"]
    )


def build_conceded_lines(team_data):
    return build_lines_from_values(
        team_data["conceded_values"]
    )


# =========================================================
# CRUZAMENTO
# =========================================================

def build_cross_lines( produced_team, opponent_team ):
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
        produced_team["averages"]
    )

    conceded_avg = (
        opponent_team[
            "conceded_averages"
        ]
    )

    for metric, label, threshold in LINE_DEFINITIONS:
        own_result = line_result(
            produced_values.get(
                metric,
                []
            ),
            threshold
        )

        conceded_result = line_result(
            opponent_conceded.get(
                metric,
                []
            ),
            threshold
        )

        own_rate = own_result.get("rate")
        conceded_rate = conceded_result.get(
            "rate"
        )

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
                sum(rates) / len(rates),
                1
            )
        else:
            cross_rate = None

        averages = [
            value
            for value in (
                produced_avg.get(metric),
                conceded_avg.get(metric)
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
            "produced": {
                "average": produced_avg.get(metric),
                "hits": own_result["hits"],
                "games": own_result["games"],
                "rate": own_rate
            },
            "opponent_conceded": {
                "average": conceded_avg.get(metric),
                "hits": conceded_result["hits"],
                "games": conceded_result["games"],
                "rate": conceded_rate
            },
            "cross_average": cross_average,
            "cross_rate": cross_rate
        })

    return result


# =========================================================
# TENDÊNCIA
# =========================================================

def build_trend_lines( cross_5, cross_10 ):
    result = []

    map_5 = {
        (
            item.get("metric"),
            item.get("line")
        ): item
        for item in cross_5
    }

    map_10 = {
        (
            item.get("metric"),
            item.get("line")
        ): item
        for item in cross_10
    }

    keys = []

    for key in map_10:
        if key not in keys:
            keys.append(key)

    for key in map_5:
        if key not in keys:
            keys.append(key)

    for key in keys:
        item_5 = map_5.get(key) or {}
        item_10 = map_10.get(key) or {}
        base = item_10 or item_5

        rate_5 = item_5.get("cross_rate")
        rate_10 = item_10.get("cross_rate")

        difference = None
        trend = "sem_dados"

        if (
            rate_5 is not None
            and rate_10 is not None
        ):
            difference = round(
                rate_5 - rate_10,
                1
            )

            if difference > 5:
                trend = "subindo"
            elif difference < -5:
                trend = "enfraquecendo"
            else:
                trend = "mantida"

        result.append({
            "metric": base.get("metric"),
            "label": base.get("label"),
            "line": base.get("line"),
            "recent_5": item_5,
            "recent_10": item_10,
            "difference": difference,
            "trend": trend
        })

    return result


def football_data_get(path, params=None, timeout=12):
    if not FOOTBALL_DATA_KEY:
        raise RuntimeError(
            "FOOTBALL_DATA_KEY não configurada no Render."
        )

    url = (
        f"{FOOTBALL_DATA_BASE}/"
        f"{path.lstrip('/')}"
    )

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {FOOTBALL_DATA_KEY}",
            "Accept": "application/json"
        },
        params=params or {},
        timeout=timeout
    )

    try:
        payload = response.json()
    except Exception:
        payload = {
            "message": "Resposta não-JSON da nova API."
        }

    if response.status_code >= 400:
        message = ""
        if isinstance(payload, dict):
            message = str(
                payload.get("message")
                or payload.get("error")
                or ""
            ).strip()

        raise RuntimeError(
            f"Nova API HTTP {response.status_code}"
            + (f": {message}" if message else "")
        )

    return payload



def football_data_get_cached(path, params=None, ttl=FOOTBALL_DATA_CACHE_SECONDS):
    params = params or {}
    key = (path, tuple(sorted((str(k), str(v)) for k, v in params.items())))
    now = time.time()
    cached = FOOTBALL_DATA_CACHE.get(key)
    if cached and now - cached["created_at"] < ttl:
        return cached["data"]
    data = football_data_get(path, params=params)
    FOOTBALL_DATA_CACHE[key] = {"created_at": now, "data": data}
    return data


def normalize_team_name(value):
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    stop = {"fc","cf","sc","ac","as","club","calcio","football","futebol"}
    return " ".join(t for t in value.split() if t not in stop)


def team_name_similarity(a, b):
    a, b = normalize_team_name(a), normalize_team_name(b)
    if not a or not b: return 0.0
    if a == b: return 1.0
    if a in b or b in a: return 0.95
    return SequenceMatcher(None, a, b).ratio()


def parse_utc_timestamp(value):
    if not value: return None
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def find_external_fixture(pitch_fixture):
    home = pitch_fixture.get("home_team") or {}
    away = pitch_fixture.get("away_team") or {}
    kickoff_ts = parse_utc_timestamp(pitch_fixture.get("time_utc"))
    if not kickoff_ts: return None
    payload = football_data_get_cached("fixtures", params={
        "start_time": kickoff_ts - 39600,
        "end_time": kickoff_ts + 39600,
        "status": "all",
        "per_page": 100,
        "lang": "pt"
    })
    fixtures = payload.get("data") or [] if isinstance(payload, dict) else []
    best, best_score = None, -1.0
    for fixture in fixtures:
        teams = fixture.get("teams") or {}
        eh, ea = teams.get("home") or {}, teams.get("away") or {}
        hs = team_name_similarity(home.get("name"), eh.get("name"))
        aas = team_name_similarity(away.get("name"), ea.get("name"))
        ext_ts = fixture.get("kickoff_ts") or parse_utc_timestamp(fixture.get("kickoff_utc"))
        time_score = 0.0 if ext_ts is None else max(0.0, 1.0 - abs(int(ext_ts)-kickoff_ts)/21600)
        score = hs*0.4 + aas*0.4 + time_score*0.2
        if hs >= 0.62 and aas >= 0.62 and score > best_score:
            best, best_score = fixture, score
    return best


def current_external_season_start(external_fixture):
    league = external_fixture.get("league") or {}
    league_id = league.get("id")
    kickoff_ts = external_fixture.get("kickoff_ts") or parse_utc_timestamp(external_fixture.get("kickoff_utc"))
    if not kickoff_ts: return None
    kickoff_dt = datetime.fromtimestamp(int(kickoff_ts), tz=ZoneInfo("UTC"))
    season_label = None
    if league_id:
        try:
            payload = football_data_get_cached(f"leagues/{league_id}", params={"lang":"pt"}, ttl=3600)
            data = payload.get("data") or {} if isinstance(payload, dict) else {}
            for season in data.get("seasons") or []:
                if season.get("current") is True:
                    season_label = str(season.get("season") or "").strip()
                    break
        except Exception:
            pass
    if season_label:
        years = re.findall(r"\d{2,4}", season_label)
        if years:
            y = int(years[0]) + (2000 if len(years[0]) == 2 else 0)
            month = 7 if "/" in season_label else 1
            return int(datetime(y, month, 1, tzinfo=ZoneInfo("UTC")).timestamp())
    y = kickoff_dt.year - (1 if kickoff_dt.month < 7 else 0)
    return int(datetime(y, 7, 1, tzinfo=ZoneInfo("UTC")).timestamp())


def external_side_value(obj, side):
    return number(obj.get(side)) if isinstance(obj, dict) else None


def external_fixture_values(fixture, team_id):
    teams = fixture.get("teams") or {}
    home, away = teams.get("home") or {}, teams.get("away") or {}
    side = "home" if home.get("id") == team_id else "away" if away.get("id") == team_id else None
    if not side:
        return {k:None for k in ("goals","corners","shots","sot","yellow_cards","red_cards","cards","fouls")}
    goals = external_side_value(fixture.get("goals"), side)
    corners = external_side_value(fixture.get("corners"), side)
    side_cards = (fixture.get("cards") or {}).get(side) or {}
    yellow = number(side_cards.get("yellow")); red = number(side_cards.get("red"))
    cards = None if yellow is None and red is None else (yellow or 0)+(red or 0)
    stats = fixture.get("statistics") or fixture.get("stats") or {}
    sot = external_side_value(stats.get("shots_on_target"), side)
    off = external_side_value(stats.get("shots_off_target"), side)
    shots = None
    for key in ("shots","total_shots","shots_total","total_attempts","attempts"):
        shots = external_side_value(stats.get(key), side)
        if shots is not None: break
    if shots is None and sot is not None and off is not None:
        shots = sot + off
    fouls = None
    for key in ("fouls","fouls_committed","total_fouls"):
        fouls = external_side_value(stats.get(key), side)
        if fouls is not None: break
    return {"goals":goals,"corners":corners,"shots":shots,"sot":sot,"yellow_cards":yellow,"red_cards":red,"cards":cards,"fouls":fouls}


def external_opponent_id(fixture, team_id):
    teams = fixture.get("teams") or {}; h, a = teams.get("home") or {}, teams.get("away") or {}
    if h.get("id") == team_id: return a.get("id")
    if a.get("id") == team_id: return h.get("id")
    return None


def external_team_average(team_id, current_external_id, limit, venue, season_start_ts, current_kickoff_ts):
    keys = ["goals","corners","shots","sot","yellow_cards","red_cards","cards","fouls"]
    payload = football_data_get_cached(f"teams/{team_id}/fixtures", params={
        "status":"finished", "start_time":season_start_ts, "end_time":current_kickoff_ts,
        "include":"stats", "per_page":50, "lang":"pt"
    })
    fixtures = payload.get("data") or [] if isinstance(payload, dict) else []
    selected=[]; seen=set()
    for fixture in fixtures:
        fid=fixture.get("id"); teams=fixture.get("teams") or {}; h=teams.get("home") or {}; a=teams.get("away") or {}
        if not fid or fid == current_external_id or fid in seen: continue
        if str(fixture.get("status") or "").lower() != "finished": continue
        if venue == "home" and h.get("id") != team_id: continue
        if venue == "away" and a.get("id") != team_id: continue
        seen.add(fid); selected.append(fixture)
        if len(selected) >= limit: break
    produced={k:[] for k in keys}; conceded={k:[] for k in keys}; history=[]
    for fixture in selected:
        own=external_fixture_values(fixture, team_id); oid=external_opponent_id(fixture, team_id)
        opp=external_fixture_values(fixture, oid) if oid else {k:None for k in keys}
        for k in keys: produced[k].append(own.get(k)); conceded[k].append(opp.get(k))
        teams=fixture.get("teams") or {}; h=teams.get("home") or {}; a=teams.get("away") or {}
        history.append({"match_id":fixture.get("id"),"home":h.get("name", ""),"away":a.get("name", ""),"produced":own,"conceded":opp})
    return {
        "matches_used":len(history),"venue":venue,
        "averages":{k:average(v) for k,v in produced.items()},
        "coverage":{k:len([x for x in v if x is not None]) for k,v in produced.items()},
        "values":produced,
        "conceded_averages":{k:average(v) for k,v in conceded.items()},
        "conceded_coverage":{k:len([x for x in v if x is not None]) for k,v in conceded.items()},
        "conceded_values":conceded,"history":history
    }


def prepare_samples_hybrid(pitch_fixture, fixture_id):
    external_fixture = find_external_fixture(pitch_fixture)
    if not external_fixture:
        league=pitch_fixture.get("league") or {}; home=pitch_fixture.get("home_team") or {}; away=pitch_fixture.get("away_team") or {}
        samples=prepare_samples(league.get("id"), home.get("id"), away.get("id"), fixture_id)
        samples["history_source"]="PITCHAPI"
        return samples
    teams=external_fixture.get("teams") or {}; eh=teams.get("home") or {}; ea=teams.get("away") or {}
    home_id, away_id = eh.get("id"), ea.get("id")
    ext_id=external_fixture.get("id"); kickoff_ts=external_fixture.get("kickoff_ts") or parse_utc_timestamp(external_fixture.get("kickoff_utc"))
    start_ts=current_external_season_start(external_fixture)
    if not all((home_id,away_id,ext_id,kickoff_ts,start_ts)):
        raise RuntimeError("Não foi possível montar o recorte da temporada atual.")
    with ThreadPoolExecutor(max_workers=2) as ex:
        hf=ex.submit(external_team_average,home_id,ext_id,10,"home",start_ts,kickoff_ts)
        af=ex.submit(external_team_average,away_id,ext_id,10,"away",start_ts,kickoff_ts)
        home10, away10 = hf.result(), af.result()
    return {"home_10":home10,"away_10":away10,"home_5":slice_team_data(home10,5),"away_5":slice_team_data(away10,5),"history_source":"5DOLLARFOOTBALLAPI"}


@app.get("/api/debug/team-history")
def debug_team_history():
    """ Diagnóstico seguro do histórico da 5DollarFootballAPI. Não expõe nenhuma chave. Mostra apenas partidas e contagens. Exemplo: /api/debug/team-history?team_id=1767 """
    team_id_raw = str(request.args.get("team_id", "")).strip()

    if not team_id_raw.isdigit():
        return jsonify({
            "ok": False,
            "error": "Informe team_id numérico."
        }), 400

    team_id = int(team_id_raw)

    # Janela propositalmente ampla dentro do limite do plano Free:
    # últimos 3 meses até agora.
    now_ts = int(time.time())
    start_ts = now_ts - (92 * 24 * 60 * 60)

    try:
        payload_all = football_data_get(
            f"teams/{team_id}/fixtures",
            params={
                "status": "all",
                "start_time": start_ts,
                "end_time": now_ts + (7 * 24 * 60 * 60),
                "per_page": 50,
                "lang": "pt"
            }
        )

        payload_finished = football_data_get(
            f"teams/{team_id}/fixtures",
            params={
                "status": "finished",
                "start_time": start_ts,
                "end_time": now_ts,
                "per_page": 50,
                "lang": "pt"
            }
        )

        all_rows = (
            payload_all.get("data") or []
            if isinstance(payload_all, dict)
            else []
        )
        finished_rows = (
            payload_finished.get("data") or []
            if isinstance(payload_finished, dict)
            else []
        )

        def compact(rows):
            result = []

            for fixture in rows:
                if not isinstance(fixture, dict):
                    continue

                teams = fixture.get("teams") or {}
                home = teams.get("home") or {}
                away = teams.get("away") or {}
                league = fixture.get("league") or {}

                if home.get("id") == team_id:
                    venue = "home"
                elif away.get("id") == team_id:
                    venue = "away"
                else:
                    venue = "unknown"

                result.append({
                    "id": fixture.get("id"),
                    "kickoff_utc": fixture.get("kickoff_utc"),
                    "status": fixture.get("status"),
                    "league": league.get("name"),
                    "home": home.get("name"),
                    "away": away.get("name"),
                    "venue_for_team": venue,
                    "goals": fixture.get("goals"),
                    "corners": fixture.get("corners"),
                    "cards": fixture.get("cards")
                })

            return result

        finished_compact = compact(finished_rows)

        return jsonify({
            "ok": True,
            "configured": bool(FOOTBALL_DATA_KEY),
            "team_id": team_id,
            "window_days": 92,
            "all_count": len(all_rows),
            "finished_count": len(finished_rows),
            "finished_home_count": len([
                row for row in finished_compact
                if row.get("venue_for_team") == "home"
            ]),
            "finished_away_count": len([
                row for row in finished_compact
                if row.get("venue_for_team") == "away"
            ]),
            "all": compact(all_rows),
            "finished": finished_compact,
            "pagination_all": (
                payload_all.get("pagination")
                if isinstance(payload_all, dict)
                else None
            ),
            "pagination_finished": (
                payload_finished.get("pagination")
                if isinstance(payload_finished, dict)
                else None
            )
        })

    except Exception as error:
        return jsonify({
            "ok": False,
            "configured": bool(FOOTBALL_DATA_KEY),
            "team_id": team_id,
            "error": str(error)
        }), 502


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
        "version": "HYBRID-TODAY-V12.1-DIAG"
    })


# =========================================================
# PARTIDAS DE HOJE
# =========================================================

def match_is_today_brazil( match, today ):
    time_utc = match.get("time_utc")

    if time_utc:
        local_day = local_match_day(
            time_utc
        )

        if local_day:
            return local_day == today

    raw_date = clean_text(
        match.get("date")
    )

    if raw_date:
        return raw_date[:10] == today

    return False


def extract_leagues(data):
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    return (
        data.get("leagues")
        or data.get("items")
        or []
    )


def season_candidates( league, today ):
    try:
        year = int(today[:4])
    except Exception:
        return []

    preferred = [
        f"{year}/{year + 1}",
        str(year),
        f"{year - 1}/{year}"
    ]

    available = league.get("seasons") or []

    if not isinstance(available, list):
        available = []

    result = []

    for season in preferred:
        if season in available:
            result.append(season)

    # Se a lista de temporadas estiver atrasada ou em
    # outro formato, tenta também as duas primeiras
    # temporadas anunciadas pela própria API.
    for season in available[:2]:
        if season and season not in result:
            result.append(str(season))

    return result[:3]


def league_matches_for_season( league, season, today ):
    league_id = league.get("id")

    if not league_id:
        return []

    try:
        season_param = quote(
            str(season),
            safe=""
        )

        data = api_get(
            f"v1/leagues/"
            f"{league_id}/matches"
            f"?season={season_param}&status=all"
        )

    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    result = []

    for match in data.get("matches") or []:
        if not match_is_today_brazil(
            match,
            today
        ):
            continue

        item = dict(match)

        current_league = (
            item.get("league")
            or {}
        )

        if not current_league:
            item["league"] = {
                "id": league.get("id"),
                "name": league.get(
                    "name",
                    "Competição"
                ),
                "image_url": league.get(
                    "image_url",
                    ""
                )
            }

        result.append(item)

    return result


def fixtures_from_all_leagues( today ):
    try:
        data = api_get("v1/leagues")
    except Exception:
        return []

    leagues = extract_leagues(data)

    if not leagues:
        return []

    jobs = []

    for league in leagues:
        if not isinstance(league, dict):
            continue

        seasons = season_candidates(
            league,
            today
        )

        for season in seasons:
            jobs.append(
                (league, season)
            )

    matches = []
    seen_ids = set()

    with ThreadPoolExecutor(
        max_workers=6
    ) as executor:

        futures = {
            executor.submit(
                league_matches_for_season,
                league,
                season,
                today
            ): (
                league.get("id"),
                season
            )
            for league, season in jobs
        }

        for future in as_completed(
            futures
        ):
            try:
                league_matches = (
                    future.result()
                )
            except Exception:
                continue

            for match in league_matches:
                match_id = match.get("id")

                if not match_id:
                    continue

                if match_id in seen_ids:
                    continue

                seen_ids.add(match_id)
                matches.append(match)

    return matches


@app.get("/api/debug/football-data")
def debug_football_data():
    result = {
        "configured": bool(
            FOOTBALL_DATA_KEY
        ),
        "status": None,
        "today": {
            "count": 0,
            "lecce": [],
            "roma": []
        }
    }

    if not FOOTBALL_DATA_KEY:
        return jsonify({
            **result,
            "ok": False,
            "error": (
                "FOOTBALL_DATA_KEY não configurada."
            )
        }), 500

    try:
        status_payload = football_data_get(
            "status"
        )

        status_data = (
            status_payload.get("data")
            if isinstance(
                status_payload,
                dict
            )
            else None
        )

        # Nunca devolvemos a chave.
        result["status"] = status_data

        fixtures_payload = football_data_get(
            "fixtures",
            params={
                "status": "all",
                "per_page": 100,
                "lang": "pt"
            }
        )

        fixtures = []

        if isinstance(
            fixtures_payload,
            dict
        ):
            fixtures = (
                fixtures_payload.get("data")
                or []
            )

        result["today"]["count"] = len(
            fixtures
        )

        for fixture in fixtures:
            if not isinstance(
                fixture,
                dict
            ):
                continue

            teams = (
                fixture.get("teams")
                or {}
            )

            home = (
                teams.get("home")
                or {}
            )

            away = (
                teams.get("away")
                or {}
            )

            compact = {
                "fixture_id": fixture.get(
                    "id"
                ),
                "kickoff_utc": fixture.get(
                    "kickoff_utc"
                ),
                "status": fixture.get(
                    "status"
                ),
                "league": (
                    fixture.get("league")
                    or {}
                ).get("name"),
                "home": {
                    "id": home.get("id"),
                    "name": home.get("name")
                },
                "away": {
                    "id": away.get("id"),
                    "name": away.get("name")
                }
            }

            names = " ".join([
                str(
                    home.get("name")
                    or ""
                ),
                str(
                    away.get("name")
                    or ""
                )
            ]).lower()

            if "lecce" in names:
                result[
                    "today"
                ][
                    "lecce"
                ].append(
                    compact
                )

            if "roma" in names:
                result[
                    "today"
                ][
                    "roma"
                ].append(
                    compact
                )

        result["ok"] = True

        return jsonify(result)

    except Exception as error:
        result["ok"] = False
        result["error"] = str(error)

        return jsonify(result), 502


@app.get("/api/fixtures/today")
def fixtures_today():
    """ Lista de hoje: 1) 5DollarFootballAPI = fonte ampla do calendário do dia. 2) PitchAPI = fornece o ID usado pela análise. 3) Só exibimos como clicável o jogo que conseguiu parear com PitchAPI. Isso evita mostrar um jogo que depois quebraria ao abrir a análise. """
    try:
        now_local = datetime.now(
            ZoneInfo(TIMEZONE)
        )
        today = now_local.strftime("%Y-%m-%d")
        now_timestamp = time.time()

        if (
            FIXTURES_CACHE["date"] == today
            and (
                now_timestamp
                - FIXTURES_CACHE["created_at"]
                < FIXTURES_CACHE_SECONDS
            )
        ):
            return jsonify({
                "mode": "live",
                "message": "",
                "date": today,
                "timezone": TIMEZONE,
                "source": "cache",
                "fixtures": FIXTURES_CACHE["matches"]
            })

        # -------------------------------------------------
        # 1. Calendário amplo da nova API
        # -------------------------------------------------
        external_payload = football_data_get_cached(
            "fixtures",
            params={
                "status": "all",
                "per_page": 100,
                "lang": "pt"
            },
            ttl=120
        )

        if not isinstance(
            external_payload,
            dict
        ):
            external_fixtures = []
        else:
            external_fixtures = (
                external_payload.get("data")
                or []
            )

        external_today = []

        for fixture in external_fixtures:
            if not isinstance(
                fixture,
                dict
            ):
                continue

            kickoff_utc = (
                fixture.get("kickoff_utc")
            )

            if (
                kickoff_utc
                and local_match_day(
                    kickoff_utc
                ) != today
            ):
                continue

            teams = (
                fixture.get("teams")
                or {}
            )
            home = (
                teams.get("home")
                or {}
            )
            away = (
                teams.get("away")
                or {}
            )

            if (
                not home.get("name")
                or not away.get("name")
            ):
                continue

            external_today.append(
                fixture
            )

        # -------------------------------------------------
        # 2. Catálogo PitchAPI em torno do dia local
        # -------------------------------------------------
        pitch_matches = []
        seen_pitch_ids = set()

        dates_to_check = [
            (
                now_local
                - timedelta(days=1)
            ).strftime("%Y-%m-%d"),
            today,
            (
                now_local
                + timedelta(days=1)
            ).strftime("%Y-%m-%d")
        ]

        pitch_warnings = []

        for date_value in dates_to_check:
            try:
                data = api_get(
                    f"v1/date/{date_value}?status=all"
                )
            except Exception as error:
                pitch_warnings.append(
                    f"{date_value}: {error}"
                )
                continue

            if not isinstance(data, dict):
                continue

            for match in (
                data.get("matches")
                or []
            ):
                if not isinstance(
                    match,
                    dict
                ):
                    continue

                match_id = match.get("id")

                if (
                    not match_id
                    or match_id
                    in seen_pitch_ids
                ):
                    continue

                if not match_is_today_brazil(
                    match,
                    today
                ):
                    continue

                seen_pitch_ids.add(
                    match_id
                )
                pitch_matches.append(
                    match
                )

        # -------------------------------------------------
        # 3. Pareamento: nova API -> PitchAPI
        # -------------------------------------------------
        normalized = []
        used_pitch_ids = set()
        unmatched = []

        for external in external_today:
            teams = (
                external.get("teams")
                or {}
            )
            ext_home = (
                teams.get("home")
                or {}
            )
            ext_away = (
                teams.get("away")
                or {}
            )

            ext_ts = (
                external.get("kickoff_ts")
                or parse_utc_timestamp(
                    external.get(
                        "kickoff_utc"
                    )
                )
            )

            best_match = None
            best_score = -1.0

            for pitch in pitch_matches:
                pitch_id = pitch.get("id")

                if (
                    not pitch_id
                    or pitch_id
                    in used_pitch_ids
                ):
                    continue

                p_home = (
                    pitch.get("home_team")
                    or {}
                )
                p_away = (
                    pitch.get("away_team")
                    or {}
                )

                home_score = (
                    team_name_similarity(
                        ext_home.get("name"),
                        p_home.get("name")
                    )
                )
                away_score = (
                    team_name_similarity(
                        ext_away.get("name"),
                        p_away.get("name")
                    )
                )

                pitch_ts = (
                    parse_utc_timestamp(
                        pitch.get("time_utc")
                    )
                )

                if (
                    ext_ts is None
                    or pitch_ts is None
                ):
                    time_score = 0.5
                else:
                    difference = abs(
                        int(ext_ts)
                        - int(pitch_ts)
                    )

                    if difference > 43200:
                        time_score = 0.0
                    else:
                        time_score = max(
                            0.0,
                            1.0
                            - (
                                difference
                                / 21600
                            )
                        )

                score = (
                    home_score * 0.45
                    + away_score * 0.45
                    + time_score * 0.10
                )

                if (
                    home_score >= 0.70
                    and away_score >= 0.70
                    and score > best_score
                ):
                    best_match = pitch
                    best_score = score

            if best_match is None:
                unmatched.append({
                    "home": ext_home.get(
                        "name",
                        ""
                    ),
                    "away": ext_away.get(
                        "name",
                        ""
                    )
                })
                continue

            used_pitch_ids.add(
                best_match.get("id")
            )

            item = normalize_match(
                best_match
            )

            # Se a PitchAPI não trouxer o nome da liga,
            # aproveita somente o nome visual da fonte ampla.
            ext_league = (
                external.get("league")
                or {}
            )

            if (
                item.get("league")
                in (
                    "",
                    "Competição"
                )
                and ext_league.get("name")
            ):
                item["league"] = (
                    ext_league.get("name")
                )

            normalized.append(item)

        normalized.sort(
            key=lambda item: (
                item.get("time")
                or "99:99",
                str(item.get("id") or "")
            )
        )

        FIXTURES_CACHE["date"] = today
        FIXTURES_CACHE["created_at"] = (
            now_timestamp
        )
        FIXTURES_CACHE["matches"] = (
            normalized
        )

        return jsonify({
            "mode": "live",
            "message": "",
            "date": today,
            "timezone": TIMEZONE,
            "source": (
                "5DOLLARFOOTBALLAPI"
                "+PITCHAPI-MAPPED"
            ),
            "fixtures": normalized,
            "external_today": len(
                external_today
            ),
            "mapped": len(normalized),
            "unmatched_count": len(
                unmatched
            ),
            "pitch_warnings": (
                pitch_warnings
            )
        })

    except Exception as error:
        return jsonify({
            "mode": "error",
            "message": str(error),
            "date": "",
            "timezone": TIMEZONE,
            "fixtures": []
        }), 502


# =========================================================
# PREPARAR AMOSTRAS
# =========================================================

def prepare_samples( league_id, home_id, away_id, fixture_id ):
    home_10 = team_average(
        league_id,
        home_id,
        fixture_id,
        10,
        "home"
    )

    away_10 = team_average(
        league_id,
        away_id,
        fixture_id,
        10,
        "away"
    )

    home_5 = slice_team_data(
        home_10,
        5
    )

    away_5 = slice_team_data(
        away_10,
        5
    )

    return {
        "home_10": home_10,
        "away_10": away_10,
        "home_5": home_5,
        "away_5": away_5
    }


# =========================================================
# CONSTRUIR ANÁLISE
# =========================================================

def build_analysis_payload( fixture_id, sample ):
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

    league = fixture.get("league") or {}
    home = fixture.get("home_team") or {}
    away = fixture.get("away_team") or {}

    league_id = league.get("id")
    home_id = home.get("id")
    away_id = away.get("id")

    match_context = (
        build_match_context(
            fixture
        )
    )

    h2h = get_h2h(fixture_id)

    samples = prepare_samples_hybrid(
        fixture,
        fixture_id
    )

    home_10 = samples["home_10"]
    away_10 = samples["away_10"]
    home_5 = samples["home_5"]
    away_5 = samples["away_5"]

    home_cross_10 = (
        build_cross_lines(
            home_10,
            away_10
        )
    )

    away_cross_10 = (
        build_cross_lines(
            away_10,
            home_10
        )
    )

    home_cross_5 = (
        build_cross_lines(
            home_5,
            away_5
        )
    )

    away_cross_5 = (
        build_cross_lines(
            away_5,
            home_5
        )
    )

    home_trends = (
        build_trend_lines(
            home_cross_5,
            home_cross_10
        )
    )

    away_trends = (
        build_trend_lines(
            away_cross_5,
            away_cross_10
        )
    )

    if sample == 5:
        home_data = home_5
        away_data = away_5
        home_cross = home_cross_5
        away_cross = away_cross_5
    else:
        home_data = home_10
        away_data = away_10
        home_cross = home_cross_10
        away_cross = away_cross_10

    h = home_data["averages"]
    a = away_data["averages"]

    return {
        "source": "PITCHAPI + 5DOLLARFOOTBALLAPI",
        "history_source": samples.get("history_source"),
        "version": "HYBRID-TODAY-V12.1-DIAG",
        "sample_size": sample,
        "match_info": match_context,
        "h2h": h2h,
        "home": {
            "id": home_id,
            "name": home.get("name", "Mandante"),
            "logo": home.get("image_url", ""),
            "venue": "home",
            "matches_used": home_data[
                "matches_used"
            ],
            "matches_5": home_5[
                "matches_used"
            ],
            "matches_10": home_10[
                "matches_used"
            ],
            "coverage": home_data[
                "coverage"
            ],
            "averages": h,
            "conceded": home_data[
                "conceded_averages"
            ],
            "conceded_coverage": home_data[
                "conceded_coverage"
            ]
        },
        "away": {
            "id": away_id,
            "name": away.get("name", "Visitante"),
            "logo": away.get("image_url", ""),
            "venue": "away",
            "matches_used": away_data[
                "matches_used"
            ],
            "matches_5": away_5[
                "matches_used"
            ],
            "matches_10": away_10[
                "matches_used"
            ],
            "coverage": away_data[
                "coverage"
            ],
            "averages": a,
            "conceded": away_data[
                "conceded_averages"
            ],
            "conceded_coverage": away_data[
                "conceded_coverage"
            ]
        },
        "stats": [
            {
                "label": "Gols",
                "home": h.get("goals"),
                "away": a.get("goals")
            },
            {
                "label": "Escanteios",
                "home": h.get("corners"),
                "away": a.get("corners")
            },
            {
                "label": "Finalizações",
                "home": h.get("shots"),
                "away": a.get("shots")
            },
            {
                "label": "Chutes no gol",
                "home": h.get("sot"),
                "away": a.get("sot")
            },
            {
                "label": "🟨 Amarelos",
                "home": h.get(
                    "yellow_cards"
                ),
                "away": a.get(
                    "yellow_cards"
                )
            },
            {
                "label": "🟥 Vermelhos",
                "home": h.get(
                    "red_cards"
                ),
                "away": a.get(
                    "red_cards"
                )
            },
            {
                "label": "Faltas",
                "home": h.get("fouls"),
                "away": a.get("fouls")
            }
        ],
        "lines": {
            "home": build_lines(
                home_data
            ),
            "away": build_lines(
                away_data
            )
        },
        "conceded_lines": {
            "home": build_conceded_lines(
                home_data
            ),
            "away": build_conceded_lines(
                away_data
            )
        },
        "cross": {
            "home": home_cross,
            "away": away_cross
        },
        "cross_samples": {
            "last_5": {
                "home": home_cross_5,
                "away": away_cross_5
            },
            "last_10": {
                "home": home_cross_10,
                "away": away_cross_10
            }
        },
        "trends": {
            "home": home_trends,
            "away": away_trends
        }
    }


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
        return jsonify(
            build_analysis_payload(
                fixture_id,
                sample
            )
        )
    except Exception as error:
        return jsonify({
            "source": "PITCHAPI + 5DOLLARFOOTBALLAPI",
            "version": "HYBRID-TODAY-V12.1-DIAG",
            "sample_size": sample,
            "match_info": {},
            "h2h": empty_h2h(),
            "stats": [],
            "lines": {},
            "conceded_lines": {},
            "cross": {},
            "cross_samples": {},
            "trends": {},
            "error": str(error)
        }), 502


# =========================================================
# LINHAS
# =========================================================

@app.get("/api/lines/<fixture_id>")
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

    if sample not in (5, 10):
        sample = 10

    try:
        data = build_analysis_payload(
            fixture_id,
            sample
        )

        return jsonify({
            "sample_size": sample,
            "version": data["version"],
            "match_info": data["match_info"],
            "h2h": data["h2h"],
            "home": {
                "name": data["home"]["name"],
                "venue": data["home"]["venue"],
                "matches_used": data[
                    "home"
                ]["matches_used"],
                "matches_5": data[
                    "home"
                ]["matches_5"],
                "matches_10": data[
                    "home"
                ]["matches_10"],
                "lines": data[
                    "lines"
                ]["home"],
                "conceded_lines": data[
                    "conceded_lines"
                ]["home"]
            },
            "away": {
                "name": data["away"]["name"],
                "venue": data["away"]["venue"],
                "matches_used": data[
                    "away"
                ]["matches_used"],
                "matches_5": data[
                    "away"
                ]["matches_5"],
                "matches_10": data[
                    "away"
                ]["matches_10"],
                "lines": data[
                    "lines"
                ]["away"],
                "conceded_lines": data[
                    "conceded_lines"
                ]["away"]
            },
            "cross": data["cross"],
            "cross_samples": data[
                "cross_samples"
            ],
            "trends": data["trends"]
        })

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 502


# =========================================================
# DIAGNÓSTICO DAS DATAS
# =========================================================

@app.get("/api/debug/dates")
def debug_dates():
    try:
        now_local = datetime.now(
            ZoneInfo(TIMEZONE)
        )

        dates_to_check = [
            (
                now_local
                - timedelta(days=1)
            ).strftime("%Y-%m-%d"),
            now_local.strftime(
                "%Y-%m-%d"
            ),
            (
                now_local
                + timedelta(days=1)
            ).strftime("%Y-%m-%d")
        ]

        result = {}

        for date_value in dates_to_check:
            try:
                data = api_get(
                    f"v1/date/{date_value}?status=all"
                )

                if isinstance(data, dict):
                    api_matches = (
                        data.get("matches")
                        or []
                    )
                else:
                    api_matches = []

                matches = []

                for match in api_matches:
                    home = (
                        match.get("home_team")
                        or {}
                    )

                    away = (
                        match.get("away_team")
                        or {}
                    )

                    league = (
                        match.get("league")
                        or {}
                    )

                    time_utc = (
                        match.get("time_utc")
                    )

                    matches.append({
                        "id": match.get("id"),
                        "league": league.get(
                            "name"
                        ),
                        "home": home.get("name"),
                        "away": away.get("name"),
                        "api_date": match.get(
                            "date"
                        ),
                        "time_utc": time_utc,
                        "hora_brasilia": (
                            match_time(time_utc)
                        ),
                        "dia_brasilia": (
                            local_match_day(
                                time_utc
                            )
                        ),
                        "status": match.get(
                            "status"
                        )
                    })

                result[date_value] = {
                    "total": len(api_matches),
                    "matches": matches
                }

            except Exception as error:
                result[date_value] = {
                    "total": 0,
                    "matches": [],
                    "error": str(error)
                }

        return jsonify({
            "ok": True,
            "timezone": TIMEZONE,
            "agora_brasilia": (
                now_local.isoformat()
            ),
            "datas": result
        })

    except Exception as error:
        return jsonify({
            "ok": False,
            "error": str(error)
        }), 500


# =========================================================
# DIAGNÓSTICO DAS TEMPORADAS
# =========================================================

@app.get("/api/debug/seasons")
def debug_seasons():
    try:
        now_local = datetime.now(
            ZoneInfo(TIMEZONE)
        )

        today = now_local.strftime(
            "%Y-%m-%d"
        )

        data = api_get("v1/leagues")
        leagues = extract_leagues(data)

        result = []

        for league in leagues:
            if not isinstance(league, dict):
                continue

            result.append({
                "id": league.get("id"),
                "name": league.get("name"),
                "seasons": league.get(
                    "seasons"
                ) or [],
                "selected": season_candidates(
                    league,
                    today
                )
            })

        return jsonify({
            "ok": True,
            "date": today,
            "total_leagues": len(result),
            "leagues": result
        })

    except Exception as error:
        return jsonify({
            "ok": False,
            "error": str(error)
        }), 500


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
