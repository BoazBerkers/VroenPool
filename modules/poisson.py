"""
Poisson Distribution Module for WK2026 Predictor
Converts odds into expected goals and builds score probability matrices.
"""

from typing import Tuple, Dict
from scipy.stats import poisson
import math


def build_score_matrix(
    lambda_a: float,
    lambda_b: float,
    max_goals: int = 5
) -> Dict[Tuple[int, int], float]:
    """
    Build a score probability matrix using Poisson distribution.

    Args:
        lambda_a: Expected goals for team A
        lambda_b: Expected goals for team B
        max_goals: Maximum goals to calculate (default 5, covers 0-5)

    Returns:
        Dict mapping (goals_a, goals_b) to probability
    """
    matrix = {}

    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            # P(A scores x) * P(B scores y)
            prob_a = poisson.pmf(x, lambda_a)
            prob_b = poisson.pmf(y, lambda_b)
            matrix[(x, y)] = prob_a * prob_b

    return matrix


def odds_to_lambdas(
    win_prob_a: float,
    draw_prob: float,
    win_prob_b: float,
    total_goals_estimate: float = None
) -> Tuple[float, float]:
    """
    Estimate expected goals (lambdas) from match odds.

    Uses a simplified approach:
    - Total goals estimate comes from Over/Under market
    - Win probability split determines team strength

    Args:
        win_prob_a: Probability team A wins (0-1)
        draw_prob: Probability of draw (0-1)
        win_prob_b: Probability team B wins (0-1)
        total_goals_estimate: Expected total goals (default: auto-calculated)

    Returns:
        Tuple of (lambda_a, lambda_b)
    """
    # Normalize probabilities
    total_prob = win_prob_a + draw_prob + win_prob_b
    if total_prob == 0:
        return 1.5, 1.5

    win_prob_a /= total_prob
    draw_prob /= total_prob
    win_prob_b /= total_prob

    # Estimate total goals if not provided
    if total_goals_estimate is None:
        # Typical match: ~2.6 goals
        total_goals_estimate = 2.6

    # Split goals by team strength
    # Team A is expected to score a fraction proportional to their win probability
    a_strength = win_prob_a + (draw_prob * 0.5)  # Draw counts half for A
    b_strength = win_prob_b + (draw_prob * 0.5)

    total_strength = a_strength + b_strength
    if total_strength == 0:
        total_strength = 1.0

    lambda_a = total_goals_estimate * (a_strength / total_strength)
    lambda_b = total_goals_estimate * (b_strength / total_strength)

    return round(lambda_a, 2), round(lambda_b, 2)


def calculate_over_under_threshold(
    lambda_a: float,
    lambda_b: float,
    threshold: float = 2.5
) -> Tuple[float, float]:
    """
    Calculate probability of Over/Under for a given threshold.

    Args:
        lambda_a: Expected goals for team A
        lambda_b: Expected goals for team B
        threshold: Goal threshold (default 2.5)

    Returns:
        Tuple of (prob_over, prob_under)
    """
    total_goals_lambda = lambda_a + lambda_b

    # Approximate: P(total > threshold)
    prob_over = 1.0 - poisson.cdf(int(threshold), total_goals_lambda)
    prob_under = poisson.cdf(int(threshold), total_goals_lambda)

    return round(prob_over, 3), round(prob_under, 3)
