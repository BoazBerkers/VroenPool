"""
WK2026 Schedule module - manages match schedule and filtering.
TODO: Replace with actual user schedule export.
"""

from datetime import datetime
from typing import List, Dict, Optional
import json
from pathlib import Path


# Sample WK2026 group stage matches (first few)
# TODO: Load from data/schedule.json once user provides it
SAMPLE_SCHEDULE = [
    {
        "id": 1,
        "date": "2026-06-11T21:00Z",
        "team_a": "Mexico",
        "team_b": "South Africa",
        "group": "A",
        "stage": "group",
        "stadium": "AT&T Stadium",
        "altitude_m": 127,
    },
    {
        "id": 2,
        "date": "2026-06-12T18:00Z",
        "team_a": "France",
        "team_b": "Denmark",
        "group": "D",
        "stage": "group",
        "stadium": "Soldier Field",
        "altitude_m": 181,
    },
    {
        "id": 3,
        "date": "2026-06-14T22:00Z",
        "team_a": "Netherlands",
        "team_b": "Japan",
        "group": "F",
        "stage": "group",
        "stadium": "Arlington Stadium",
        "altitude_m": 127,
    },
    {
        "id": 4,
        "date": "2026-06-15T19:00Z",
        "team_a": "Deutschland",
        "team_b": "Curacao",
        "group": "G",
        "stage": "group",
        "stadium": "Estadio Azteca",
        "altitude_m": 2240,
    },
]


def get_all_matches() -> List[Dict]:
    """Get all matches in schedule."""
    return SAMPLE_SCHEDULE


def get_match_by_id(match_id: int) -> Optional[Dict]:
    """Get a specific match by ID."""
    for match in SAMPLE_SCHEDULE:
        if match["id"] == match_id:
            return match
    return None


def get_upcoming_matches(hours_ahead: int = 24) -> List[Dict]:
    """
    Get matches in the next N hours.

    Args:
        hours_ahead: Number of hours to look ahead

    Returns:
        List of upcoming matches
    """
    now = datetime.utcnow()
    upcoming = []

    for match in SAMPLE_SCHEDULE:
        match_time = datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
        if 0 <= (match_time - now).total_seconds() <= hours_ahead * 3600:
            upcoming.append(match)

    return sorted(upcoming, key=lambda m: m["date"])


def get_next_match() -> Optional[Dict]:
    """Get the very next upcoming match."""
    upcoming = get_upcoming_matches(hours_ahead=999)  # Look far ahead
    if upcoming:
        return upcoming[0]
    return None


def get_matches_by_group(group: str) -> List[Dict]:
    """Get all matches in a specific group."""
    return [m for m in SAMPLE_SCHEDULE if m["group"] == group]


def get_matches_by_stage(stage: str) -> List[Dict]:
    """Get matches by stage (group, round16, quarter, semi, final)."""
    return [m for m in SAMPLE_SCHEDULE if m["stage"] == stage]


def load_schedule_from_file(filepath: str = None) -> None:
    """
    Load schedule from JSON file (user export).

    Args:
        filepath: Path to schedule JSON file (default: data/schedule.json)
    """
    global SAMPLE_SCHEDULE

    if filepath is None:
        filepath = Path(__file__).parent.parent / "data" / "schedule.json"

    if Path(filepath).exists():
        with open(filepath, "r") as f:
            SAMPLE_SCHEDULE = json.load(f)


# Try loading from file on module import
try:
    load_schedule_from_file()
except Exception:
    pass  # Use SAMPLE_SCHEDULE if file not found
