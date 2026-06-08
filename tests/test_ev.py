"""
Comprehensive tests for EV Calculator
Tests all scoring scenarios from requirements §9
"""

import pytest
from modules.ev_calculator import calculate_points, expected_value, best_prediction
from modules.poisson import build_score_matrix, odds_to_lambdas
import math


class TestCalculatePoints:
    """Test the calculate_points function with all scoring rules."""

    def test_exact_score(self):
        """Exact score match = 200 pts."""
        assert calculate_points(2, 1, 2, 1) == 200
        assert calculate_points(0, 0, 0, 0) == 200
        assert calculate_points(3, 2, 3, 2) == 200

    def test_correct_draw_exact(self):
        """Exact draw match (same score both predicted and actual) = 200 pts."""
        assert calculate_points(1, 1, 1, 1) == 200

    def test_correct_draw_other_score(self):
        """Predicted draw (1-1) but result is different draw = 100 pts."""
        assert calculate_points(1, 1, 0, 0) == 100
        assert calculate_points(1, 1, 2, 2) == 100
        assert calculate_points(0, 0, 3, 3) == 100
        assert calculate_points(2, 2, 1, 1) == 100

    def test_winner_plus_goals(self):
        """Winner correct + exact goals for one team = 95 pts."""
        # A wins, B goals correct
        assert calculate_points(2, 0, 3, 0) == 95
        # A wins, A goals correct
        assert calculate_points(2, 0, 2, 1) == 95
        # B wins, B goals correct
        assert calculate_points(0, 2, 1, 2) == 95
        # A wins, A goals correct
        assert calculate_points(3, 1, 3, 2) == 95

    def test_winner_only(self):
        """Only winner correct = 75 pts."""
        assert calculate_points(3, 1, 1, 0) == 75
        assert calculate_points(2, 0, 3, 1) == 75  # A wins both, no exact goals
        assert calculate_points(2, 1, 4, 2) == 75

    def test_one_team_goals_consolation(self):
        """One team goals correct (winner wrong) = 20 pts."""
        assert calculate_points(1, 2, 1, 0) == 20
        # A=2 predicted, A=3 actual, B=0 both → A wins in both, so 75 not 20
        # Need a case where A goals match but winner is wrong
        assert calculate_points(2, 1, 2, 3) == 20  # A=2 correct, B wins in result
        assert calculate_points(1, 2, 3, 2) == 20  # B=2 correct, A wins in prediction

    def test_nothing_correct(self):
        """Nothing correct = 0 pts."""
        assert calculate_points(2, 1, 0, 3) == 0
        assert calculate_points(1, 0, 2, 2) == 0
        assert calculate_points(3, 2, 0, 1) == 0

    def test_draw_not_predicted_but_happens(self):
        """Draw happens but wasn't predicted = 20 or 0 depending on team goals."""
        # Predicted A win (2-1), result draw with A goals match (2-2)
        assert calculate_points(2, 1, 2, 2) == 20  # A goals match but winner wrong
        # Predicted A win (3-0), result draw (1-1)
        assert calculate_points(3, 0, 1, 1) == 0  # Neither A nor B goals match


class TestExpectedValue:
    """Test the expected_value function."""

    def test_certain_outcome(self):
        """When one outcome has 100% probability, EV should equal that score's points."""
        matrix = {(2, 1): 1.0}  # Certain 2-1
        ev = expected_value(2, 1, matrix)
        assert ev == 200  # Exact match

    def test_mixed_outcomes(self):
        """Test EV with multiple outcomes."""
        matrix = {
            (2, 1): 0.5,  # 50% chance of exact match = 200 pts
            (3, 2): 0.5,  # 50% chance: A wins in both, no exact goals = 75 pts
        }
        ev = expected_value(2, 1, matrix)
        assert ev == 137.5  # (0.5 * 200) + (0.5 * 75)

    def test_draw_prediction_with_draw_outcomes(self):
        """Test draw prediction against multiple draw outcomes."""
        matrix = {
            (1, 1): 0.3,  # Exact match
            (0, 0): 0.4,  # Different draw
            (2, 2): 0.3,  # Different draw
        }
        ev = expected_value(1, 1, matrix)
        # (0.3 * 200) + (0.4 * 100) + (0.3 * 100) = 60 + 40 + 30 = 130
        assert ev == 130

    def test_ev_decreases_with_worse_prediction(self):
        """EV should be lower for a random guess vs optimal prediction."""
        matrix = {
            (2, 1): 0.6,
            (2, 0): 0.4,
        }
        ev_best = expected_value(2, 1, matrix)  # Favors 2-1
        ev_random = expected_value(0, 5, matrix)  # Random guess
        assert ev_best > ev_random


class TestBestPrediction:
    """Test the best_prediction optimizer."""

    def test_single_outcome(self):
        """When single outcome, best prediction should match it exactly."""
        matrix = {(2, 1): 1.0}
        pred_a, pred_b, max_ev = best_prediction(matrix)
        assert pred_a == 2
        assert pred_b == 1
        assert max_ev == 200

    def test_multiple_outcomes(self):
        """Test that best_prediction chooses the optimal score."""
        matrix = {
            (2, 0): 0.5,  # Most likely
            (1, 0): 0.3,
            (0, 1): 0.2,
        }
        pred_a, pred_b, max_ev = best_prediction(matrix)
        # Should predict 2-0 (highest probability and gives points)
        assert pred_a == 2
        assert pred_b == 0
        assert max_ev > 0

    def test_draw_preference_in_coin_flip(self):
        """When win probabilities are close, draw might be optimal."""
        # Symmetric matrix (coin flip scenario)
        matrix = {
            (1, 0): 0.33,
            (0, 1): 0.33,
            (1, 1): 0.34,  # Draw slightly more likely
        }
        pred_a, pred_b, max_ev = best_prediction(matrix)
        # Should prefer 1-1 as it gives 100 pts for draw + has slight probability edge
        assert pred_a == 1
        assert pred_b == 1


class TestPoissonMatrix:
    """Test Poisson score matrix builder."""

    def test_probability_sums_to_one(self):
        """Matrix probabilities should sum to approximately 1.0."""
        matrix = build_score_matrix(2.0, 1.5, max_goals=5)
        total_prob = sum(matrix.values())
        assert 0.95 < total_prob <= 1.0  # Allow small rounding error

    def test_matrix_dimensions(self):
        """Matrix should have correct dimensions."""
        matrix = build_score_matrix(2.0, 1.5, max_goals=4)
        assert len(matrix) == 25  # 5x5 (0-4)

        matrix = build_score_matrix(2.0, 1.5, max_goals=5)
        assert len(matrix) == 36  # 6x6 (0-5)

    def test_higher_lambda_higher_probability(self):
        """Higher lambda should give higher probability for more goals."""
        matrix_low = build_score_matrix(1.0, 1.0, max_goals=5)
        matrix_high = build_score_matrix(3.0, 3.0, max_goals=5)

        # Probability of 3+ goals should be higher in high matrix
        prob_low = sum(p for (x, y), p in matrix_low.items() if x + y >= 3)
        prob_high = sum(p for (x, y), p in matrix_high.items() if x + y >= 3)
        assert prob_high > prob_low

    def test_asymmetric_lambdas(self):
        """Asymmetric lambdas should favor one team's scoring."""
        matrix = build_score_matrix(3.0, 1.0, max_goals=5)
        # Sum probability of A scoring 3+ vs B scoring 3+
        prob_a_3plus = sum(p for (x, y), p in matrix.items() if x >= 3)
        prob_b_3plus = sum(p for (x, y), p in matrix.items() if y >= 3)
        assert prob_a_3plus > prob_b_3plus


class TestOddsToLambdas:
    """Test odds conversion to expected goals."""

    def test_equal_odds_equal_lambdas(self):
        """Equal win probabilities should give similar lambdas."""
        lambda_a, lambda_b = odds_to_lambdas(0.33, 0.34, 0.33)
        assert abs(lambda_a - lambda_b) < 0.2  # Similar but not identical

    def test_strong_favorite(self):
        """Strong favorite should have higher lambda."""
        lambda_a, lambda_b = odds_to_lambdas(0.70, 0.15, 0.15)
        assert lambda_a > lambda_b

    def test_underdog(self):
        """Underdog should have lower lambda."""
        lambda_a, lambda_b = odds_to_lambdas(0.15, 0.15, 0.70)
        assert lambda_b > lambda_a

    def test_with_total_goals_hint(self):
        """Providing total goals estimate should scale lambdas."""
        lambda_a, lambda_b = odds_to_lambdas(0.5, 0.0, 0.5, total_goals_estimate=3.0)
        total = lambda_a + lambda_b
        assert 2.8 < total < 3.2  # Should be close to 3.0

    def test_lambdas_are_positive(self):
        """Lambdas should always be positive (can't have negative goals)."""
        for win_a in [0.2, 0.5, 0.8]:
            for draw in [0.0, 0.1, 0.2]:
                win_b = 1.0 - win_a - draw
                if win_b < 0:
                    continue
                lambda_a, lambda_b = odds_to_lambdas(win_a, draw, win_b)
                assert lambda_a > 0
                assert lambda_b > 0


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_pipeline_deutschland_vs_curacao(self):
        """Test full pipeline: odds -> lambdas -> matrix -> best prediction."""
        # Deutschland is heavy favorite, Curaçao is underdog
        lambda_a, lambda_b = odds_to_lambdas(
            win_prob_a=0.85,
            draw_prob=0.10,
            win_prob_b=0.05,
            total_goals_estimate=2.8
        )
        assert lambda_a > lambda_b

        matrix = build_score_matrix(lambda_a, lambda_b)
        pred_a, pred_b, max_ev = best_prediction(matrix)

        # Prediction should have Curaçao (B) with 0 or 1 goal
        assert pred_b <= 1
        # Max EV should be reasonable (positive)
        assert max_ev > 50

    def test_full_pipeline_netherlands_vs_japan(self):
        """Test pipeline with closer teams (Netherlands vs Japan from wireframe)."""
        lambda_a, lambda_b = odds_to_lambdas(
            win_prob_a=0.53,
            draw_prob=0.26,
            win_prob_b=0.21,
            total_goals_estimate=2.4
        )

        matrix = build_score_matrix(lambda_a, lambda_b)
        pred_a, pred_b, max_ev = best_prediction(matrix)

        # Prediction should favor Netherlands
        assert pred_a >= pred_b or (pred_a == pred_b == 1)  # Either NL wins or 1-1
        assert max_ev > 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
