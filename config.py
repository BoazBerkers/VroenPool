"""
VroenWK2026 Pool Configuration
Defines the scoring system for match predictions.
"""

SCORING = {
    "exact_score": 200,          # Predicted score matches exactly
    "correct_draw": 100,         # Predicted draw AND result is a draw (any score)
    "winner_plus_goals": 95,     # Winner correct + exact goals for one team
    "winner_only": 75,           # Only the winner was correct
    "one_team_goals": 20,        # Exact goals for one team (winner doesn't matter)
    "nothing": 0,                # Nothing correct
}

BONUS = {
    "champion": 300,             # Bonus for predicting tournament winner
    "topscorer": 300,            # Bonus for predicting tournament top scorer
}

# Pool metadata
POOL_NAME = "VroenWK2026"
TOTAL_GROUP_MATCHES = 48
TOTAL_KNOCKOUT_MATCHES = 16
TOTAL_MATCHES = 64
