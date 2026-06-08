"""
Data fetcher module with mocked API responses.
Fetches odds, injuries, team stats, and match context.
"""

from typing import Dict, List, Any, Optional
from modules.cache import cache_get, cache_set, get_cache_age


# Mock data for testing without live APIs
MOCK_ODDS = {
    "nederland_japan": {
        "home_win": 0.53,
        "draw": 0.26,
        "away_win": 0.21,
        "over_2_5": 0.45,
        "under_2_5": 0.55,
    },
    "deutschland_curacao": {
        "home_win": 0.85,
        "draw": 0.10,
        "away_win": 0.05,
        "over_2_5": 0.68,
        "under_2_5": 0.32,
    },
}

MOCK_INJURIES = {
    "Nederland": [
        {"player": "Simons", "status": "out", "position": "Defender"},
        {"player": "De Ligt", "status": "out", "position": "Defender"},
    ],
    "Japan": [
        {"player": "Mitoma", "status": "out", "position": "Forward"},
        {"player": "Minamino", "status": "out", "position": "Midfielder"},
    ],
    "Deutschland": [],
    "Curacao": [],
}

MOCK_FORM = {
    "Nederland": [
        {"result": "W", "goals_for": 2, "goals_against": 1},
        {"result": "W", "goals_for": 3, "goals_against": 0},
        {"result": "D", "goals_for": 1, "goals_against": 1},
        {"result": "W", "goals_for": 2, "goals_against": 0},
        {"result": "W", "goals_for": 1, "goals_against": 0},
    ],
    "Japan": [
        {"result": "W", "goals_for": 2, "goals_against": 0},
        {"result": "W", "goals_for": 1, "goals_against": 1},
        {"result": "W", "goals_for": 3, "goals_against": 1},
        {"result": "L", "goals_for": 0, "goals_against": 2},
        {"result": "W", "goals_for": 2, "goals_against": 0},
    ],
    "Deutschland": [
        {"result": "W", "goals_for": 4, "goals_against": 0},
        {"result": "W", "goals_for": 2, "goals_against": 1},
        {"result": "W", "goals_for": 3, "goals_against": 0},
        {"result": "W", "goals_for": 5, "goals_against": 1},
        {"result": "W", "goals_for": 2, "goals_against": 0},
    ],
    "Curacao": [
        {"result": "L", "goals_for": 0, "goals_against": 4},
        {"result": "D", "goals_for": 1, "goals_against": 1},
        {"result": "L", "goals_for": 1, "goals_against": 2},
        {"result": "W", "goals_for": 1, "goals_against": 0},
        {"result": "L", "goals_for": 0, "goals_against": 3},
    ],
}

MOCK_CONTEXT = {
    "nederland_japan": {
        "stadium": "Arlington Stadium",
        "altitude_m": 127,
        "home_country": "Netherlands",
        "neutral": True,
    },
    "deutschland_curacao": {
        "stadium": "Estadio Azteca",
        "altitude_m": 2240,
        "home_country": "Mexico",
        "neutral": True,
    },
}


def fetch_odds(match_key: str, use_mock: bool = True) -> Dict[str, Any]:
    """
    Fetch odds for a match (currently mocked).

    Args:
        match_key: Match identifier (e.g., 'nederland_japan')
        use_mock: Use mock data (for testing)

    Returns:
        Dict with win probabilities and over/under odds
    """
    if use_mock:
        return MOCK_ODDS.get(
            match_key.lower(),
            {
                "home_win": 0.40,
                "draw": 0.25,
                "away_win": 0.35,
                "over_2_5": 0.45,
                "under_2_5": 0.55,
            },
        )

    # TODO: Integrate The Odds API
    cache_key = f"odds_{match_key}"
    cached = cache_get(cache_key, ttl_seconds=1800)  # 30 min TTL
    if cached:
        return cached

    # Placeholder for real API call
    return {}


def fetch_injuries(team_name: str, use_mock: bool = True) -> List[Dict[str, Any]]:
    """
    Fetch injury information for a team.

    Args:
        team_name: Team name
        use_mock: Use mock data

    Returns:
        List of injured players with status
    """
    if use_mock:
        return MOCK_INJURIES.get(
            team_name,
            [],
        )

    # TODO: Integrate API-Football or Claude API
    cache_key = f"injuries_{team_name}"
    cached = cache_get(cache_key, ttl_seconds=1800)  # 30 min TTL
    if cached:
        return cached

    return []


def fetch_recent_form(
    team_name: str,
    last_n: int = 5,
    use_mock: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetch recent match form for a team.

    Args:
        team_name: Team name
        last_n: Number of recent matches
        use_mock: Use mock data

    Returns:
        List of last N matches with result and goals
    """
    if use_mock:
        return MOCK_FORM.get(team_name, [])[:last_n]

    # TODO: Integrate API-Football
    cache_key = f"form_{team_name}"
    cached = cache_get(cache_key, ttl_seconds=21600)  # 6 hour TTL
    if cached:
        return cached

    return []


def fetch_context(
    match_key: str,
    use_mock: bool = True,
) -> Dict[str, Any]:
    """
    Fetch match context (stadium, altitude, etc).

    Args:
        match_key: Match identifier
        use_mock: Use mock data

    Returns:
        Context dict with stadium, altitude, etc.
    """
    if use_mock:
        return MOCK_CONTEXT.get(
            match_key.lower(),
            {
                "stadium": "Unknown",
                "altitude_m": 0,
                "home_country": None,
                "neutral": False,
            },
        )

    # Data from schedule.json
    return {}


def fetch_all_match_data(
    match_key: str,
    team_a: str,
    team_b: str,
    use_mock: bool = True,
) -> Dict[str, Any]:
    """
    Fetch all data for a match in one call.

    Args:
        match_key: Match identifier
        team_a: Team A name
        team_b: Team B name
        use_mock: Use mock data

    Returns:
        Aggregated dict with odds, injuries, form, context
    """
    return {
        "odds": fetch_odds(match_key, use_mock),
        "injuries_a": fetch_injuries(team_a, use_mock),
        "injuries_b": fetch_injuries(team_b, use_mock),
        "form_a": fetch_recent_form(team_a, use_mock=use_mock),
        "form_b": fetch_recent_form(team_b, use_mock=use_mock),
        "context": fetch_context(match_key, use_mock),
    }
