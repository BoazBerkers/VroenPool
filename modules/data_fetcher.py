"""
Data fetcher module with real and mocked API responses.
Fetches odds, injuries, team stats, and match context.
"""

import os
from typing import Dict, List, Any, Optional
from modules.cache import cache_get, cache_set, get_cache_age
import requests
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")


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


def fetch_odds(match_key: str, use_mock: bool = False) -> Dict[str, Any]:
    """
    Fetch odds for a match from The Odds API.

    Args:
        match_key: Match identifier (e.g., 'nederland_japan')
        use_mock: Use mock data (for testing when API unavailable)

    Returns:
        Dict with win probabilities and over/under odds (2.5, 3.5, 4.5)
    """
    # Check cache first
    cache_key = f"odds_{match_key}"
    cached = cache_get(cache_key, ttl_seconds=1800)  # 30 min TTL
    if cached:
        return cached

    # Try real API
    if ODDS_API_KEY and not use_mock:
        try:
            url = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": "eu",
                "markets": "h2h,totals",
                "oddsFormat": "decimal",
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            # API returns list of events directly (not nested under "events" key)
            events = data if isinstance(data, list) else data.get("events", [])

            # Find matching event
            for event in events:
                # Try to match by team names in event
                event_name = event.get("name", "").lower()
                home_team = event.get("home_team", "").lower()
                away_team = event.get("away_team", "").lower()

                # Match by team names or match_key
                match_found = (
                    match_key.lower() in event_name
                    or (home_team and away_team and match_key.lower().replace("_", " ") in f"{home_team} {away_team}")
                    or ("nederland" in event_name and "japan" in event_name)
                )

                if not match_found:
                    continue

                # Extract odds from bookmakers
                for bookmaker in event.get("bookmakers", []):
                    markets = {m["key"]: m for m in bookmaker.get("markets", [])}

                    h2h_market = markets.get("h2h", {})
                    totals_market = markets.get("totals", {})

                    if h2h_market:
                        outcomes = {o["name"]: o["price"] for o in h2h_market.get("outcomes", [])}
                        home_odds = outcomes.get(event.get("home_team", ""), 1.0)
                        away_odds = outcomes.get(event.get("away_team", ""), 1.0)
                        draw_odds = outcomes.get("Draw", 1.0)

                        # Convert decimal odds to probabilities
                        home_prob = 1.0 / home_odds if home_odds > 0 else 0.33
                        away_prob = 1.0 / away_odds if away_odds > 0 else 0.33
                        draw_prob = 1.0 / draw_odds if draw_odds > 0 else 0.33

                        # Normalize
                        total = home_prob + away_prob + draw_prob
                        if total > 0:
                            home_prob /= total
                            away_prob /= total
                            draw_prob /= total

                        # Extract over/under for multiple thresholds
                        over_under = {
                            "over_2_5": 0.5,
                            "under_2_5": 0.5,
                            "over_3_5": 0.45,
                            "under_3_5": 0.55,
                            "over_4_5": 0.35,
                            "under_4_5": 0.65,
                        }

                        for outcome in totals_market.get("outcomes", []):
                            point = outcome.get("point")
                            odds = outcome.get("price", 1.0)
                            prob = 1.0 / odds if odds > 0 else 0.5
                            name = outcome.get("name", "").lower()

                            if point == 2.5:
                                if "over" in name:
                                    over_under["over_2_5"] = prob
                                else:
                                    over_under["under_2_5"] = prob
                            elif point == 3.5:
                                if "over" in name:
                                    over_under["over_3_5"] = prob
                                else:
                                    over_under["under_3_5"] = prob
                            elif point == 4.5:
                                if "over" in name:
                                    over_under["over_4_5"] = prob
                                else:
                                    over_under["under_4_5"] = prob

                        result = {
                            "home_win": home_prob,
                            "draw": draw_prob,
                            "away_win": away_prob,
                            "over_2_5": over_under["over_2_5"],
                            "under_2_5": over_under["under_2_5"],
                            "over_3_5": over_under.get("over_3_5", 0.45),
                            "under_3_5": over_under.get("under_3_5", 0.55),
                            "over_4_5": over_under.get("over_4_5", 0.35),
                            "under_4_5": over_under.get("under_4_5", 0.65),
                        }
                        cache_set(cache_key, result)
                        return result

        except (requests.RequestException, KeyError, ValueError, TypeError) as e:
            print(f"Odds API error: {e}. Falling back to mock data.")

    # Fallback to mock
    return MOCK_ODDS.get(
        match_key.lower(),
        {
            "home_win": 0.40,
            "draw": 0.25,
            "away_win": 0.35,
            "over_2_5": 0.45,
            "under_2_5": 0.55,
            "over_3_5": 0.40,
            "under_3_5": 0.60,
            "over_4_5": 0.30,
            "under_4_5": 0.70,
        },
    )


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
