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


def match_date(value):
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
            "%d/%m/%Y"
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


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


# =========================================================
# CONTEXTO DA PARTIDA
# =========================================================

def build_match_context(fixture):
    referee = clean_text(
        fixture.get("referee")
    )

    stadium = clean_text(
        fixture.get("stadium")
    )

    round_name = clean_text(
        fixture.get("round_name")
    )

    date = clean_text(
        fixture.get("date")
    )

    status = clean_text(
        fixture.get("status")
    )

    kickoff = match_time(
        fixture.get("time_utc")
    )

    return {
        "referee":
            referee or None,

        "stadium":
            stadium or None,

        "round":
            round_name or None,

        "date":
            date or None,

        "time":
            kickoff or None,

        "status":
            status or None
    }


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
                return item.get("home")

            return item.get("away")

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

def get_card_breakdown(
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

    yellow = 0
    red = 0

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

        if event_type == "yellowcard":
            yellow += 1

        elif event_type == "redcard":
            red += 1

    return {
        "yellow_cards":
            float(yellow),

        "red_cards":
            float(red),

        "cards":
            float(
                yellow + red
            )
    }


# =========================================================
# H2H ESTATÍSTICO
# =========================================================

H2H_STATS_LIMIT = 5


def empty_h2h():
    return {
        "available": False,
        "total_matches": 0,
        "home_wins": 0,
        "draws": 0,
        "away_wins": 0,
        "recent_matches": [],
        "stats_analysis": {
            "matches_checked": 0,
            "matches_with_detailed_stats": 0,
            "goals": [],
            "corners": [],
            "sot": [],
            "yellow_cards": [],
            "fouls": []
        }
    }


def total_line_result(
    values,
    threshold,
    label
):
    valid = [
        float(value)
        for value in values
        if value is not None
    ]

    if not valid:
        return {
            "label":
                label,

            "line":
                threshold,

            "hits":
                0,

            "games":
                0,

            "rate":
                None
        }

    hits = sum(
        1
        for value in valid
        if value > threshold
    )

    return {
        "label":
            label,

        "line":
            threshold,

        "hits":
            hits,

        "games":
            len(valid),

        "rate":
            round(
                hits /
                len(valid) *
                100,
                1
            )
    }


def find_match_id_by_date(
    time_utc,
    home_team_id,
    away_team_id
):
    if not time_utc:
        return None

    try:
        dt = datetime.fromisoformat(
            time_utc.replace(
                "Z",
                "+00:00"
            )
        )

        date_value = dt.strftime(
            "%Y-%m-%d"
        )

    except Exception:
        return None

    try:
        data = api_get(
            f"v1/date/{date_value}"
        )

    except Exception:
        return None

    if not isinstance(
        data,
        dict
    ):
        return None

    for match in (
        data.get("matches")
        or []
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
            == home_team_id
            and
            away.get("id")
            == away_team_id
        ):
            return match.get("id")

    return None


def h2h_detailed_values(
    match_id,
    home_team_id,
    away_team_id
):
    if not match_id:
        return {
            "corners": None,
            "sot": None,
            "yellow_cards": None,
            "fouls": None
        }

    stats = get_stats(
        match_id
    )

    home_corners = find_exact_stat(
        stats,
        [
            "corners",
            "corner_kicks",
            "corner kicks"
        ],
        True
    )

    away_corners = find_exact_stat(
        stats,
        [
            "corners",
            "corner_kicks",
            "corner kicks"
        ],
        False
    )

    home_fouls = find_exact_stat(
        stats,
        [
            "fouls",
            "fouls_committed",
            "fouls committed"
        ],
        True
    )

    away_fouls = find_exact_stat(
        stats,
        [
            "fouls",
            "fouls_committed",
            "fouls committed"
        ],
        False
    )

    home_sot = find_exact_stat(
        stats,
        [
            "shots_on_target",
            "shots on target"
        ],
        True
    )

    away_sot = find_exact_stat(
        stats,
        [
            "shots_on_target",
            "shots on target"
        ],
        False
    )

    if home_sot is None:
        home_sot = sot_from_shots(
            match_id,
            home_team_id
        )

    if away_sot is None:
        away_sot = sot_from_shots(
            match_id,
            away_team_id
        )

    home_cards = get_card_breakdown(
        match_id,
        home_team_id
    )

    away_cards = get_card_breakdown(
        match_id,
        away_team_id
    )

    if (
        home_corners is not None
        and
        away_corners is not None
    ):
        corners = (
            home_corners +
            away_corners
        )

    else:
        corners = None

    if (
        home_sot is not None
        and
        away_sot is not None
    ):
        sot = (
            home_sot +
            away_sot
        )

    else:
        sot = None

    if (
        home_fouls is not None
        and
        away_fouls is not None
    ):
        fouls = (
            home_fouls +
            away_fouls
        )

    else:
        fouls = None

    if (
        home_cards is not None
        and
        away_cards is not None
    ):
        yellow_cards = (
            home_cards[
                "yellow_cards"
            ]
            +
            away_cards[
                "yellow_cards"
            ]
        )

    else:
        yellow_cards = None

    return {
        "corners":
            corners,

        "sot":
            sot,

        "yellow_cards":
            yellow_cards,

        "fouls":
            fouls
    }


def build_h2h_stats(
    recent_matches
):
    goals_values = []
    corners_values = []
    sot_values = []
    yellow_values = []
    fouls_values = []

    detailed_checked = 0
    detailed_available = 0

    for index, match in enumerate(
        recent_matches
    ):

        score_home = number(
            match.get(
                "score_home"
            )
        )

        score_away = number(
            match.get(
                "score_away"
            )
        )

        if (
            score_home is not None
            and
            score_away is not None
        ):
            goals_values.append(
                score_home +
                score_away
            )

        if index >= H2H_STATS_LIMIT:
            continue

        home = (
            match.get("home")
            or {}
        )

        away = (
            match.get("away")
            or {}
        )

        detailed_checked += 1

        match_id = (
            match.get("match_id")
            or
            find_match_id_by_date(
                match.get(
                    "time_utc"
                ),
                home.get("id"),
                away.get("id")
            )
        )

        if not match_id:
            continue

        detailed = (
            h2h_detailed_values(
                match_id,
                home.get("id"),
                away.get("id")
            )
        )

        has_detailed_data = any(
            value is not None
            for value
            in detailed.values()
        )

        if has_detailed_data:
            detailed_available += 1

        corners_values.append(
            detailed.get(
                "corners"
            )
        )

        sot_values.append(
            detailed.get(
                "sot"
            )
        )

        yellow_values.append(
            detailed.get(
                "yellow_cards"
            )
        )

        fouls_values.append(
            detailed.get(
                "fouls"
            )
        )

    return {
        "matches_checked":
            detailed_checked,

        "matches_with_detailed_stats":
            detailed_available,

        "goals": [
            total_line_result(
                goals_values,
                0.5,
                "+0.5 Gols"
            ),

            total_line_result(
                goals_values,
                1.5,
                "+1.5 Gols"
            ),

            total_line_result(
                goals_values,
                2.5,
                "+2.5 Gols"
            )
        ],

        "corners": [
            total_line_result(
                corners_values,
                7.5,
                "+7.5 Escanteios"
            ),

            total_line_result(
                corners_values,
                8.5,
                "+8.5 Escanteios"
            )
        ],

        "sot": [
            total_line_result(
                sot_values,
                5.5,
                "+5.5 Chutes no gol"
            ),

            total_line_result(
                sot_values,
                7.5,
                "+7.5 Chutes no gol"
            )
        ],

        "yellow_cards": [
            total_line_result(
                yellow_values,
                2.5,
                "+2.5 Cartões amarelos"
            ),

            total_line_result(
                yellow_values,
                3.5,
                "+3.5 Cartões amarelos"
            )
        ],

        "fouls": [
            total_line_result(
                fouls_values,
                19.5,
                "+19.5 Faltas"
            ),

            total_line_result(
                fouls_values,
                21.5,
                "+21.5 Faltas"
            )
        ]
    }


def get_h2h(fixture_id):
    try:
        data = api_get(
            f"v1/matches/"
            f"{fixture_id}/h2h"
        )

    except Exception:
        return empty_h2h()

    if not isinstance(
        data,
        dict
    ):
        return empty_h2h()

    recent = []

    for match in (
        data.get("recent_matches")
        or []
    ):

        if not match.get(
            "finished",
            False
        ):
            continue

        home = (
            match.get("home")
            or {}
        )

        away = (
            match.get("away")
            or {}
        )

        score_home = number(
            match.get("score_home")
        )

        score_away = number(
            match.get("score_away")
        )

        if (
            score_home is None
            or
            score_away is None
        ):
            continue

        recent.append({
            "match_id":
                match.get("id"),

            "date":
                match_date(
                    match.get(
                        "time_utc"
                    )
                ),

            "time_utc":
                match.get(
                    "time_utc"
                ),

            "home": {
                "id":
                    home.get("id"),

                "name":
                    home.get(
                        "name",
                        "Mandante"
                    )
            },

            "away": {
                "id":
                    away.get("id"),

                "name":
                    away.get(
                        "name",
                        "Visitante"
                    )
            },

            "score_home":
                int(score_home),

            "score_away":
                int(score_away),

            "finished":
                True
        })

    recent.sort(
        key=lambda x: (
            x.get(
                "time_utc"
            )
            or ""
        ),
        reverse=True
    )

    recent = recent[:10]

    home_team = (
        data.get("home_team")
        or {}
    )

    away_team = (
        data.get("away_team")
        or {}
    )

    stats_analysis = (
        build_h2h_stats(
            recent
        )
    )

    return {
        "available":
            True,

        "home_team": {
            "id":
                home_team.get("id"),

            "name":
                home_team.get(
                    "name",
                    "Mandante"
                )
        },

        "away_team": {
            "id":
                away_team.get("id"),

            "name":
                away_team.get(
                    "name",
                    "Visitante"
                )
        },

        "total_matches":
            int(
                data.get(
                    "total_matches"
                )
                or 0
            ),

        "home_wins":
            int(
                data.get(
                    "home_wins"
                )
                or 0
            ),

        "draws":
            int(
                data.get(
                    "draws"
                )
                or 0
            ),

        "away_wins":
            int(
                data.get(
                    "away_wins"
                )
                or 0
            ),

        "recent_matches":
            recent,

        "stats_analysis":
            stats_analysis
    }


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

    card_data = get_card_breakdown(
        match_id,
        team_id
    )

    if card_data is None:

        yellow_cards = None
        red_cards = None
        cards = None

    else:

        yellow_cards = (
            card_data[
                "yellow_cards"
            ]
        )

        red_cards = (
            card_data[
                "red_cards"
            ]
        )

        cards = (
            card_data[
                "cards"
            ]
        )

    return {
        "goals":
            goals,

        "corners":
            corners,

        "shots":
            shots,

        "sot":
            sot,

        "yellow_cards":
            yellow_cards,

        "red_cards":
            red_cards,

        "cards":
            cards,

        "fouls":
            fouls
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
        "yellow_cards": [],
        "red_cards": [],
        "cards": [],
        "fouls": []
    }

    conceded = {
        "goals": [],
        "corners": [],
        "shots": [],
        "sot": [],
        "yellow_cards": [],
        "red_cards": [],
        "cards": [],
        "fouls": []
    }

    history = []

    for match in matches:

        own_row = team_match_values(
            match,
            team_id
        )

        opponent_id = (
            opponent_id_from_match(
                match,
                team_id
            )
        )

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
                "yellow_cards": None,
                "red_cards": None,
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

            "produced":
                own_row,

            "conceded":
                conceded_row
        })

    return {
        "matches_used":
            len(matches),

        "venue":
            venue,

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

        "values":
            produced,

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

        "conceded_values":
            conceded,

        "history":
            history
    }


# =========================================================
# RECORTE 5 JOGOS
# =========================================================

def slice_team_data(
    team_data,
    limit
):
    produced = {
        key: value[:limit]
        for key, value
        in team_data[
            "values"
        ].items()
    }

    conceded = {
        key: value[:limit]
        for key, value
        in team_data[
            "conceded_values"
        ].items()
    }

    history = (
        team_data[
            "history"
        ][:limit]
    )

    return {
        "matches_used":
            len(history),

        "venue":
            team_data.get(
                "venue"
            ),

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

        "values":
            produced,

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

        "conceded_values":
            conceded,

        "history":
            history
    }


# =========================================================
# CONTAGEM DAS LINHAS
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
            "line":
                threshold,

            "hits":
                0,

            "games":
                0,

            "rate":
                None
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
        "line":
            threshold,

        "hits":
            hits,

        "games":
            len(valid),

        "rate":
            rate
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
# CRIAR LINHAS
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
            "metric":
                metric,

            "label":
                label,

            **line_result(
                values.get(
                    metric,
                    []
                ),
                threshold
            )
        })

    return result


def build_lines(
    team_data
):
    return build_lines_from_values(
        team_data[
            "values"
        ]
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
# CRUZAMENTO
# =========================================================

def build_cross_lines(
    produced_team,
    opponent_team
):
    result = []

    produced_values = (
        produced_team[
            "values"
        ]
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

        own_rate = (
            own_result.get(
                "rate"
            )
        )

        conceded_rate = (
            conceded_result.get(
                "rate"
            )
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
            "metric":
                metric,

            "label":
                label,

            "line":
                threshold,

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

            "cross_average":
                cross_average,

            "cross_rate":
                cross_rate
        })

    return result


# =========================================================
# TENDÊNCIA 5 × 10
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

    all_keys = []

    for key in map_10:

        if key not in all_keys:
            all_keys.append(
                key
            )

    for key in map_5:

        if key not in all_keys:
            all_keys.append(
                key
            )

    for key in all_keys:

        item_10 = (
            map_10.get(key)
            or {}
        )

        item_5 = (
            map_5.get(key)
            or {}
        )

        base = (
            item_10
            or item_5
        )

        rate_5 = (
            item_5.get(
                "cross_rate"
            )
        )

        rate_10 = (
            item_10.get(
                "cross_rate"
            )
        )

        trend = "sem_dados"
        difference = None

        if (
            rate_5 is not None
            and
            rate_10 is not None
        ):

            difference = round(
                rate_5 - rate_10,
                1
            )

            if difference > 5:

                trend = "subindo"

            elif difference < -5:

                trend = (
                    "enfraquecendo"
                )

            else:

                trend = "mantida"

        result.append({
            "metric":
                base.get(
                    "metric"
                ),

            "label":
                base.get(
                    "label"
                ),

            "line":
                base.get(
                    "line"
                ),

            "recent_5":
                item_5,

            "recent_10":
                item_10,

            "difference":
                difference,

            "trend":
                trend
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
        "ok":
            True,

        "provider":
            "PITCHAPI",

        "api_configured":
            bool(API_KEY),

        "demo_mode":
            False,

        "timezone":
            TIMEZONE,

        "version":
            "H2H-STATS-V1"
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
            "mode":
                "live",

            "message":
                "",

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
            "mode":
                "error",

            "message":
                str(error),

            "fixtures":
                []
        }), 502


# =========================================================
# PREPARAR ÚLTIMOS 5 E 10
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
        "home_10":
            home_10,

        "away_10":
            away_10,

        "home_5":
            home_5,

        "away_5":
            away_5
    }


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

        league_id = (
            league.get("id")
        )

        home_id = (
            home.get("id")
        )

        away_id = (
            away.get("id")
        )

        match_context = (
            build_match_context(
                fixture
            )
        )

        h2h = get_h2h(
            fixture_id
        )

        samples = prepare_samples(
            league_id,
            home_id,
            away_id,
            fixture_id
        )

        home_10 = (
            samples["home_10"]
        )

        away_10 = (
            samples["away_10"]
        )

        home_5 = (
            samples["home_5"]
        )

        away_5 = (
            samples["away_5"]
        )

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

        h = (
            home_data[
                "averages"
            ]
        )

        a = (
            away_data[
                "averages"
            ]
        )

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

        return jsonify({
            "source":
                "PITCHAPI",

            "version":
                "H2H-STATS-V1",

            "sample_size":
                sample,

            "match_info":
                match_context,

            "h2h":
                h2h,

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

                "venue":
                    "home",

                "matches_used":
                    home_data[
                        "matches_used"
                    ],

                "matches_5":
                    home_5[
                        "matches_used"
                    ],

                "matches_10":
                    home_10[
                        "matches_used"
                    ],

                "coverage":
                    home_data[
                        "coverage"
                    ],

                "averages":
                    h,

                "conceded":
                    home_conceded,

                "conceded_coverage":
                    home_data[
                        "conceded_coverage"
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

                "venue":
                    "away",

                "matches_used":
                    away_data[
                        "matches_used"
                    ],

                "matches_5":
                    away_5[
                        "matches_used"
                    ],

                "matches_10":
                    away_10[
                        "matches_used"
                    ],

                "coverage":
                    away_data[
                        "coverage"
                    ],

                "averages":
                    a,

                "conceded":
                    away_conceded,

                "conceded_coverage":
                    away_data[
                        "conceded_coverage"
                    ]
            },

            "stats": [
                {
                    "label":
                        "Gols",

                    "home":
                        h.get(
                            "goals"
                        ),

                    "away":
                        a.get(
                            "goals"
                        )
                },

                {
                    "label":
                        "Escanteios",

                    "home":
                        h.get(
                            "corners"
                        ),

                    "away":
                        a.get(
                            "corners"
                        )
                },

                {
                    "label":
                        "Finalizações",

                    "home":
                        h.get(
                            "shots"
                        ),

                    "away":
                        a.get(
                            "shots"
                        )
                },

                {
                    "label":
                        "Chutes no gol",

                    "home":
                        h.get(
                            "sot"
                        ),

                    "away":
                        a.get(
                            "sot"
                        )
                },

                {
                    "label":
                        "🟨 Amarelos",

                    "home":
                        h.get(
                            "yellow_cards"
                        ),

                    "away":
                        a.get(
                            "yellow_cards"
                        )
                },

                {
                    "label":
                        "🟥 Vermelhos",

                    "home":
                        h.get(
                            "red_cards"
                        ),

                    "away":
                        a.get(
                            "red_cards"
                        )
                },

                {
                    "label":
                        "Faltas",

                    "home":
                        h.get(
                            "fouls"
                        ),

                    "away":
                        a.get(
                            "fouls"
                        )
                }
            ],

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

            "cross": {
                "home":
                    home_cross,

                "away":
                    away_cross
            },

            "cross_samples": {
                "last_5": {
                    "home":
                        home_cross_5,

                    "away":
                        away_cross_5
                },

                "last_10": {
                    "home":
                        home_cross_10,

                    "away":
                        away_cross_10
                }
            },

            "trends": {
                "home":
                    home_trends,

                "away":
                    away_trends
            }
        })

    except Exception as error:

        return jsonify({
            "source":
                "PITCHAPI",

            "version":
                "H2H-STATS-V1",

            "sample_size":
                sample,

            "match_info":
                {},

            "h2h":
                empty_h2h(),

            "stats":
                [],

            "lines":
                {},

            "conceded_lines":
                {},

            "cross":
                {},

            "cross_samples":
                {},

            "trends":
                {},

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

        league_id = (
            league.get("id")
        )

        home_id = (
            home.get("id")
        )

        away_id = (
            away.get("id")
        )

        match_context = (
            build_match_context(
                fixture
            )
        )

        h2h = get_h2h(
            fixture_id
        )

        samples = prepare_samples(
            league_id,
            home_id,
            away_id,
            fixture_id
        )

        home_10 = (
            samples[
                "home_10"
            ]
        )

        away_10 = (
            samples[
                "away_10"
            ]
        )

        home_5 = (
            samples[
                "home_5"
            ]
        )

        away_5 = (
            samples[
                "away_5"
            ]
        )

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

        return jsonify({
            "sample_size":
                sample,

            "version":
                "H2H-STATS-V1",

            "match_info":
                match_context,

            "h2h":
                h2h,

            "home": {
                "name":
                    home.get(
                        "name",
                        "Mandante"
                    ),

                "venue":
                    "home",

                "matches_used":
                    home_data[
                        "matches_used"
                    ],

                "matches_5":
                    home_5[
                        "matches_used"
                    ],

                "matches_10":
                    home_10[
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
                "name":
                    away.get(
                        "name",
                        "Visitante"
                    ),

                "venue":
                    "away",

                "matches_used":
                    away_data[
                        "matches_used"
                    ],

                "matches_5":
                    away_5[
                        "matches_used"
                    ],

                "matches_10":
                    away_10[
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
                    home_cross,

                "away":
                    away_cross
            },

            "cross_samples": {
                "last_5": {
                    "home":
                        home_cross_5,

                    "away":
                        away_cross_5
                },

                "last_10": {
                    "home":
                        home_cross_10,

                    "away":
                        away_cross_10
                }
            },

            "trends": {
                "home":
                    home_trends,

                "away":
                    away_trends
            }
        })

    except Exception as error:

        return jsonify({
            "error":
                str(error),

            "version":
                "H2H-STATS-V1"
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
