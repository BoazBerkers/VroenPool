"""
Strategy rule engine for WK2026 Predictor.
Applies domain-specific rules to refine EV-based predictions.
"""

from typing import Dict, Tuple, Any, List
from modules.poisson import odds_to_lambdas, build_score_matrix
from modules.ev_calculator import expected_value


def apply_strategy_rules(
    pred_a: int,
    pred_b: int,
    team_a: str,
    team_b: str,
    odds: Dict[str, float],
    injuries_a: List[Dict],
    injuries_b: List[Dict],
    context: Dict[str, Any],
    form_a: List[Dict],
    form_b: List[Dict],
) -> Tuple[int, int, str, bool]:
    """
    Apply strategy rules to potentially adjust prediction.

    Args:
        pred_a, pred_b: EV-optimal prediction
        team_a, team_b: Team names
        odds: Dict with home_win, draw, away_win probabilities
        injuries_a, injuries_b: List of injured players
        context: Match context (stadium, altitude, etc.)
        form_a, form_b: Recent form data

    Returns:
        (final_pred_a, final_pred_b, reason_text, was_override)
    """
    reason = f"EV-optimal prediction"
    was_override = False

    # Rule 1: Nul-houden hefboom (Strong favorite, weak underdog attack)
    rule_1_result = _apply_zero_hold_rule(
        pred_a, pred_b, odds, injuries_a, injuries_b, form_a, form_b
    )
    if rule_1_result:
        return rule_1_result + (True,)

    # Rule 2: Gelijkspel-anker (Coin flip scenario)
    rule_2_result = _apply_draw_anchor_rule(pred_a, pred_b, odds)
    if rule_2_result:
        return rule_2_result + (True,)

    # Rule 3: Blessure-aanpassing (Star attacker missing)
    # This modifies the underlying lambdas, so it's handled before EV calculation
    # in app.py, not here.

    # Rule 4: Late groupstage risk (Both teams qualified)
    flag_4 = _check_late_groupstage_risk(context)
    if flag_4:
        reason += " [⚠️ Late groupstage: rotation risk]"

    # Rule 5: Hoogte-nadeel (High altitude)
    flag_5 = _check_altitude_disadvantage(context)
    if flag_5:
        reason += " [⚠️ High altitude: expect lower scores]"

    return pred_a, pred_b, reason, was_override


def _apply_zero_hold_rule(
    pred_a: int,
    pred_b: int,
    odds: Dict[str, float],
    injuries_a: List[Dict],
    injuries_b: List[Dict],
    form_a: List[Dict],
    form_b: List[Dict],
) -> Tuple[int, int, str] | None:
    """
    Rule 1: Nul-houden hefboom
    If favorite has >75% win odds AND underdog has weak attack → force underdog to 0 goals.
    This shifts prediction like 2-1 → 2-0 (adds 20 pts if outcome is 2-0).
    """
    home_win = odds.get("home_win", 0.5)
    away_win = odds.get("away_win", 0.5)

    # Determine favorite and underdog
    if home_win > away_win:
        favorite_win = home_win
        underdog_form = form_b
        underdog_injuries = injuries_b
        is_favorite_home = True
    else:
        favorite_win = away_win
        underdog_form = form_a
        underdog_injuries = injuries_a
        is_favorite_home = False

    # Trigger: Favorite > 75% AND underdog avg goals < 1.2
    if favorite_win < 0.75:
        return None

    # Calculate underdog average goals from recent form
    avg_goals = sum(m["goals_for"] for m in underdog_form) / max(len(underdog_form), 1)
    if avg_goals > 1.2:
        return None

    # Check for critical injuries (attackers/midfielders)
    critical_injuries = sum(
        1
        for inj in underdog_injuries
        if inj.get("status") == "out"
        and inj.get("position") in ["Forward", "Midfielder"]
    )

    if critical_injuries == 0:
        return None

    # Apply rule: force underdog goals to 0
    if is_favorite_home:
        new_pred = (pred_a, 0)
    else:
        new_pred = (0, pred_b)

    return new_pred[0], new_pred[1], "Nul-houden hefboom (weak underdog attack)"


def _apply_draw_anchor_rule(
    pred_a: int,
    pred_b: int,
    odds: Dict[str, float],
) -> Tuple[int, int, str] | None:
    """
    Rule 2: Gelijkspel-anker
    If win probabilities are close (35-45%), recommend 1-1.
    Reasoning: 100 pts on draw + potential 200 pts on 1-1 exact.
    """
    home_win = odds.get("home_win", 0.5)
    away_win = odds.get("away_win", 0.5)
    draw = odds.get("draw", 0.0)

    # Trigger: both wins between 35-45%
    if not (0.35 < home_win < 0.45 and 0.35 < away_win < 0.45):
        return None

    # Only if draw is significant (>20%)
    if draw < 0.20:
        return None

    return 1, 1, "Gelijkspel-anker (balanced match)"


def _check_late_groupstage_risk(context: Dict[str, Any]) -> bool:
    """
    Rule 4: Late groupstage risk
    Flag if both teams are likely already qualified (matchday 3, same group).
    Returns True if risk detected (flags for conservative prediction).
    """
    # TODO: Integrate with actual group standings
    # For now, return False unless we have specific context
    return False


def _check_altitude_disadvantage(context: Dict[str, Any]) -> bool:
    """
    Rule 5: Hoogte-nadeel
    Flag if stadium > 1500m altitude.
    High altitude typically reduces goals by ~15%.
    """
    altitude_m = context.get("altitude_m", 0)
    return altitude_m > 1500


def adjust_lambdas_for_injuries(
    lambda_a: float,
    lambda_b: float,
    injuries_a: List[Dict],
    injuries_b: List[Dict],
) -> Tuple[float, float]:
    """
    Rule 3: Blessure-aanpassing
    Reduce lambda if key offensive players are missing.
    """
    # Count critical injuries (Forward/Midfielder, OUT status)
    critical_a = sum(
        1
        for inj in injuries_a
        if inj.get("status") == "out"
        and inj.get("position") in ["Forward", "Midfielder"]
    )
    critical_b = sum(
        1
        for inj in injuries_b
        if inj.get("status") == "out"
        and inj.get("position") in ["Forward", "Midfielder"]
    )

    # Apply 10% reduction per critical injury
    lambda_a *= (1 - 0.10 * min(critical_a, 2))
    lambda_b *= (1 - 0.10 * min(critical_b, 2))

    return max(0.5, lambda_a), max(0.5, lambda_b)


def adjust_lambdas_for_altitude(
    lambda_a: float,
    lambda_b: float,
    altitude_m: float,
) -> Tuple[float, float]:
    """
    Rule 5 (continued): Apply altitude reduction to lambdas.
    """
    if altitude_m > 1500:
        # Reduce by ~15%
        reduction_factor = 0.85
        lambda_a *= reduction_factor
        lambda_b *= reduction_factor

    return lambda_a, lambda_b
