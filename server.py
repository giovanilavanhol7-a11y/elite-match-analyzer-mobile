from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import os
import time
import requests
import re


app = Flask(__name__, static_folder="static")

API_KEY = os.getenv("PITCHAPI_KEY", "").strip()
API_BASE = "https://api.pitchapi.dev"
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
# CHUTES NO GOL
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


def get_league_matches_cached(
    league_id,
    season=None
):
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


def _match_fits_team_venue(
    match,
    team_id,
    venue
):
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


def recent_matches(
    league_id,
    team_id,
    current_id,
    limit,
    venue
):
    if not league_id:
        return []

    result = []
    seen_ids = set()

    # Primeiro consulta as temporadas anunciadas pela própria liga,
    # começando pelas mais recentes. Isso permite completar os 10
    # jogos com a temporada anterior quando a temporada atual ainda
    # está no começo.
    seasons = get_league_seasons(
        league_id
    )

    # Segurança: se a API não devolver temporadas, mantém o
    # comportamento antigo consultando a temporada padrão.
    season_queries = (
        seasons[:4]
        if seasons
        else [None]
    )

    for season in season_queries:
        try:
            matches = get_league_matches_cached(
                league_id,
                season
            )
        except Exception:
            continue

        ordered = list(matches)

        ordered.sort(
            key=lambda item: (
                item.get("time_utc")
                or item.get("date")
                or ""
            ),
            reverse=True
        )

        for match in ordered:
            match_id = match.get("id")

            if not match_id:
                continue

            if match_id == current_id:
                continue

            if match_id in seen_ids:
                continue

            if not _finished_match_status(
                match
            ):
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
                return result[:limit]

    # Fallback final para a temporada padrão, caso as temporadas
    # explícitas não tenham completado a amostra.
    if len(result) < limit:
        try:
            matches = get_league_matches_cached(
                league_id,
                None
            )
        except Exception:
            matches = []

        ordered = list(matches)

        ordered.sort(
            key=lambda item: (
                item.get("time_utc")
                or item.get("date")
                or ""
            ),
            reverse=True
        )

        for match in ordered:
            match_id = match.get("id")

            if not match_id:
                continue

            if match_id == current_id:
                continue

            if match_id in seen_ids:
                continue

            if not _finished_match_status(
                match
            ):
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

    for match in matches:
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

        for key in keys:
            produced[key].append(
                own_row.get(key)
            )
            conceded[key].append(
                conceded_row.get(key)
            )

        home = match.get("home_team") or {}
        away = match.get("away_team") or {}

        history.append({
            "match_id": match.get("id"),
            "home": home.get("name", ""),
            "away": away.get("name", ""),
            "produced": own_row,
            "conceded": conceded_row
        })

    return {
        "matches_used": len(matches),
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

def build_trend_lines(
    cross_5,
    cross_10
):
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
        "version": "RECENT-SEASONS-V7"
    })


# =========================================================
# PARTIDAS DE HOJE
# =========================================================

def match_is_today_brazil(
    match,
    today
):
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


def season_candidates(
    league,
    today
):
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


def league_matches_for_season(
    league,
    season,
    today
):
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


def fixtures_from_all_leagues(
    today
):
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


@app.get("/api/fixtures/today")
def fixtures_today():
    try:
        now_local = datetime.now(
            ZoneInfo(TIMEZONE)
        )

        today = now_local.strftime(
            "%Y-%m-%d"
        )

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

        matches = []
        seen_ids = set()

        # A PitchAPI trabalha com data de calendário UTC.
        # Como o site exibe horário de Brasília, consultamos
        # ontem, hoje e amanhã na API e depois mantemos apenas
        # as partidas que realmente caem em "hoje" no Brasil.
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

        errors = []

        for date_value in dates_to_check:
            try:
                data = api_get(
                    f"v1/date/{date_value}?status=all"
                )
            except Exception as error:
                errors.append(
                    f"{date_value}: {error}"
                )
                continue

            if not isinstance(data, dict):
                continue

            for match in data.get("matches") or []:
                if not match_is_today_brazil(
                    match,
                    today
                ):
                    continue

                match_id = match.get("id")

                if not match_id:
                    continue

                if match_id in seen_ids:
                    continue

                seen_ids.add(match_id)
                matches.append(match)

        matches.sort(
            key=lambda match: (
                match_time(
                    match.get("time_utc")
                )
                or "99:99",
                str(match.get("id") or "")
            )
        )

        normalized = [
            normalize_match(match)
            for match in matches
        ]

        FIXTURES_CACHE["date"] = today
        FIXTURES_CACHE["created_at"] = now_timestamp
        FIXTURES_CACHE["matches"] = normalized

        return jsonify({
            "mode": "live",
            "message": "",
            "date": today,
            "timezone": TIMEZONE,
            "source": "date-status-all",
            "fixtures": normalized,
            "api_warnings": errors
        })

    except Exception as error:
        return jsonify({
            "mode": "error",
            "message": str(error),
            "fixtures": []
        }), 502


# =========================================================
# PREPARAR AMOSTRAS
# =========================================================

def prepare_samples(
    league_id,
    home_id,
    away_id,
    fixture_id
):
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

def build_analysis_payload(
    fixture_id,
    sample
):
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

    samples = prepare_samples(
        league_id,
        home_id,
        away_id,
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
        "source": "PITCHAPI",
        "version": "RECENT-SEASONS-V7",
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
            "source": "PITCHAPI",
            "version": "RECENT-SEASONS-V7",
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
