"""
Core EV Calculator for WK2026 Match Predictor
Implements the scoring logic and expected value calculations.
"""

from typing import Tuple, Dict
from config import SCORING


def calculate_points(pred_a: int, pred_b: int, res_a: int, res_b: int) -> int:
    """
    Calculate pool points based on prediction vs actual result.

    Args:
        pred_a: Predicted goals for team A
        pred_b: Predicted goals for team B
        res_a: Actual goals for team A
        res_b: Actual goals for team B

    Returns:
        Points awarded (0-200) based on pool scoring system
    """
    a, b = pred_a, pred_b
    x, y = res_a, res_b

    # Rule 1: Exact score match
    if a == x and b == y:
        return SCORING["exact_score"]

    # Rule 2: Correct draw (both predicted draw AND result is draw)
    if a == b and x == y:
        return SCORING["correct_draw"]

    # Rule 3: Winner + one team goals exact
    winner_correct = (a > b and x > y) or (a < b and x < y)
    if winner_correct and (a == x or b == y):
        return SCORING["winner_plus_goals"]

    # Rule 4: Winner only
    if winner_correct:
        return SCORING["winner_only"]

    # Rule 5: One team goals correct (consolation)
    if a == x or b == y:
        return SCORING["one_team_goals"]

    # Rule 6: Nothing correct
    return SCORING["nothing"]


def expected_value(pred_a: int, pred_b: int, score_matrix: Dict[Tuple[int, int], float]) -> float:
    """
    Calculate expected value of a prediction across all possible outcomes.

    Args:
        pred_a: Predicted goals for team A
        pred_b: Predicted goals for team B
        score_matrix: Dict mapping (result_a, result_b) to probability

    Returns:
        Expected value in points (weighted sum across all outcomes)
    """
    ev = 0.0
    for (res_a, res_b), probability in score_matrix.items():
        points = calculate_points(pred_a, pred_b, res_a, res_b)
        ev += probability * points
    return ev


def best_prediction(score_matrix: Dict[Tuple[int, int], float]) -> Tuple[int, int, float]:
    """
    Find the prediction with maximum expected value.

    Args:
        score_matrix: Dict mapping (result_a, result_b) to probability

    Returns:
        Tuple of (pred_a, pred_b, max_ev)
    """
    best_ev = -1.0
    best_pred = (0, 0)

    for pred_a in range(6):
        for pred_b in range(6):
            ev = expected_value(pred_a, pred_b, score_matrix)
            if ev > best_ev:
                best_ev = ev
                best_pred = (pred_a, pred_b)

    return best_pred[0], best_pred[1], best_ev


def get_top_predictions(
    score_matrix: Dict[Tuple[int, int], float],
    n: int = 5,
    exclude: Tuple[int, int] = None
) -> list:
    """
    Get top N predictions ranked by EV.

    Args:
        score_matrix: Dict mapping (result_a, result_b) to probability
        n: Number of top predictions to return
        exclude: Prediction tuple to exclude from results (e.g., the best one)

    Returns:
        List of tuples [(pred_a, pred_b, ev), ...]
    """
    predictions = []

    for pred_a in range(6):
        for pred_b in range(6):
            if exclude and (pred_a, pred_b) == exclude:
                continue
            ev = expected_value(pred_a, pred_b, score_matrix)
            predictions.append((pred_a, pred_b, ev))

    # Sort by EV descending
    predictions.sort(key=lambda x: x[2], reverse=True)
    return predictions[:n]
