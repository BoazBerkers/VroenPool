"""
WK2026 Predictor - Streamlit Web Application
Main entry point for the World Cup pool predictor.
"""

import streamlit as st
from datetime import datetime
import pandas as pd
from typing import Dict, List

from schedule import get_all_matches, get_next_match
from modules.data_fetcher import fetch_all_match_data
from modules.poisson import odds_to_lambdas, build_score_matrix
from modules.ev_calculator import best_prediction, expected_value, get_top_predictions
from modules.strategy import (
    apply_strategy_rules,
    adjust_lambdas_for_injuries,
    adjust_lambdas_for_altitude,
)
from modules.cache import get_cache_age


def format_time(seconds: int) -> str:
    """Format seconds as human-readable age."""
    if seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    else:
        return f"{seconds // 3600}h ago"


def render_odds_card(odds: Dict) -> None:
    """Render odds card in sidebar/column."""
    st.subheader("Odds")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Home Win", f"{odds.get('home_win', 0) * 100:.0f}%")
    with col2:
        st.metric("Draw", f"{odds.get('draw', 0) * 100:.0f}%")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Away Win", f"{odds.get('away_win', 0) * 100:.0f}%")
    with col2:
        ou = "Under" if odds.get("under_2_5", 0.5) > odds.get("over_2_5", 0.5) else "Over"
        st.metric("O/U 2.5", ou)

    # Additional O/U markets for calibration transparency
    if odds.get("over_3_5") is not None:
        st.write("**Additional Markets:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            ou_35 = "Under" if odds.get("under_3_5", 0.5) > odds.get("over_3_5", 0.5) else "Over"
            st.caption(f"O/U 3.5: {ou_35}")
        with col2:
            ou_45 = "Under" if odds.get("under_4_5", 0.5) > odds.get("over_4_5", 0.5) else "Over"
            st.caption(f"O/U 4.5: {ou_45}")
        with col3:
            st.caption(f"(Used for calibration)")


def render_injuries_card(team_name: str, injuries: List[Dict]) -> None:
    """Render injuries card."""
    st.subheader(f"Injuries: {team_name}")
    if not injuries:
        st.write("✓ No known injuries")
    else:
        for inj in injuries:
            status_icon = "🔴" if inj.get("status") == "out" else "🟡"
            pos = inj.get("position", "?")
            st.write(f"{status_icon} {inj.get('player', '?')} ({pos})")


def render_form_card(team_name: str, form: List[Dict]) -> None:
    """Render recent form card."""
    st.subheader(f"Recent Form: {team_name}")
    if not form:
        st.write("No form data")
    else:
        form_str = " ".join(m["result"] for m in reversed(form[-5:]))
        st.write(f"Last 5: {form_str}")
        avg_goals = sum(m["goals_for"] for m in form) / len(form)
        st.write(f"Avg goals: {avg_goals:.2f}")


def render_ev_heatmap(score_matrix: Dict, best_pred: tuple = None) -> None:
    """Render EV heatmap with color gradient."""
    st.subheader("EV Heatmap: All Predictions (0-0 to 5-5)")

    # Build EV matrix
    ev_data = {}
    max_ev = 0
    for pred_a in range(6):
        row = {}
        for pred_b in range(6):
            ev = expected_value(pred_a, pred_b, score_matrix)
            row[pred_b] = round(ev, 1)
            max_ev = max(max_ev, ev)
        ev_data[pred_a] = row

    df = pd.DataFrame(ev_data).T
    df.index.name = "Team A →"
    df.columns.name = "Team B →"

    # Create color gradient: red (low EV) to green (high EV)
    def color_ev(val):
        if max_ev == 0:
            return "background-color: #f0f0f0"
        pct = val / max_ev
        if pct > 0.9:
            return "background-color: #C0DD97"  # Bright green
        elif pct > 0.8:
            return "background-color: #D4EB8F"
        elif pct > 0.7:
            return "background-color: #EAF3DE"  # Light green
        elif pct > 0.5:
            return "background-color: #FAC775"  # Yellow
        elif pct > 0.3:
            return "background-color: #F5C4B3"  # Light red
        else:
            return "background-color: #F7C1C1"  # Red

    styled_df = df.style.map(color_ev)
    st.dataframe(styled_df, use_container_width=True)

    # Legend
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.write("🟩 High EV")
    with col2:
        st.write("🟩 Good EV")
    with col3:
        st.write("🟨 Fair EV")
    with col4:
        st.write("🟥 Low EV")
    with col5:
        st.write("🟥 Poor EV")


def render_top_alternatives(
    score_matrix: Dict,
    best_pred: tuple,
    best_ev: float,
) -> None:
    """Render top 5 alternative predictions."""
    st.subheader("Top 5 Alternative Predictions")

    alternatives = get_top_predictions(score_matrix, n=5, exclude=best_pred)
    for rank, (pred_a, pred_b, ev) in enumerate(alternatives, 1):
        delta = ev - best_ev
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"{rank}. **{pred_a}-{pred_b}**")
        with col2:
            st.write(f"EV: {ev:.1f}")
        with col3:
            st.write(f"{delta:+.1f}" if delta < 0 else f"+{delta:.1f}")


def main():
    st.set_page_config(page_title="WK2026 Predictor", layout="wide")

    st.title("🏆 WK2026 Pool Predictor")
    st.subheader("VroenWK2026 Match Analysis & Recommendations")

    # Sidebar
    with st.sidebar:
        st.markdown("### Configuration")
        use_mock = st.checkbox("Use mock data", value=False)
        st.markdown("---")

        # Match selector
        all_matches = get_all_matches()
        default_match = get_next_match() or (all_matches[0] if all_matches else None)
        match_options = [
            f"{m['date'][:10]} · {m['team_a']} vs {m['team_b']}"
            for m in all_matches
        ]
        selected_idx = 0
        if default_match:
            try:
                selected_idx = all_matches.index(default_match)
            except ValueError:
                pass

        selected = st.selectbox(
            "Select Match",
            range(len(all_matches)),
            format_func=lambda i: match_options[i],
            index=selected_idx,
        )
        selected_match = all_matches[selected]

    # Main content
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        st.write(f"**{selected_match['team_a']}**")
    with col2:
        st.write("vs")
    with col3:
        st.write(f"**{selected_match['team_b']}**")

    st.caption(
        f"Date: {selected_match['date'][:10]} | "
        f"Group: {selected_match.get('group', 'KO')} | "
        f"Stadium: {selected_match.get('stadium', 'TBD')}"
    )

    # Fetch data
    match_key = (
        f"{selected_match['team_a'].lower()}_{selected_match['team_b'].lower()}"
    )
    all_data = fetch_all_match_data(
        match_key,
        selected_match["team_a"],
        selected_match["team_b"],
        use_mock=use_mock,
    )

    odds = all_data["odds"]
    injuries_a = all_data["injuries_a"]
    injuries_b = all_data["injuries_b"]
    form_a = all_data["form_a"]
    form_b = all_data["form_b"]
    context = all_data["context"]

    # Convert odds to lambdas with multi-market calibration
    total_goals_est = (
        2.6 if odds.get("under_2_5", 0.5) > 0.5 else 2.8
    )  # Estimate based on O/U 2.5
    lambda_a, lambda_b = odds_to_lambdas(
        odds.get("home_win", 0.4),
        odds.get("draw", 0.25),
        odds.get("away_win", 0.35),
        total_goals_estimate=total_goals_est,
        over_3_5=odds.get("over_3_5"),
        over_4_5=odds.get("over_4_5"),
    )

    # Apply injury adjustments
    lambda_a, lambda_b = adjust_lambdas_for_injuries(
        lambda_a, lambda_b, injuries_a, injuries_b
    )

    # Apply altitude adjustments
    altitude = context.get("altitude_m", 0)
    lambda_a, lambda_b = adjust_lambdas_for_altitude(
        lambda_a, lambda_b, altitude
    )

    # Build score matrix
    score_matrix = build_score_matrix(lambda_a, lambda_b)

    # Get best prediction
    best_pred_a, best_pred_b, best_ev = best_prediction(score_matrix)

    # Apply strategy rules
    final_a, final_b, strategy_reason, was_override = apply_strategy_rules(
        best_pred_a,
        best_pred_b,
        selected_match["team_a"],
        selected_match["team_b"],
        odds,
        injuries_a,
        injuries_b,
        context,
        form_a,
        form_b,
    )

    if was_override:
        final_ev = expected_value(final_a, final_b, score_matrix)
    else:
        final_a, final_b, final_ev = best_pred_a, best_pred_b, best_ev

    # Render recommendation
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"<div style='text-align:center; padding: 20px; "
            f"background:#f0f0f0; border-radius:10px; border: 3px solid #3B6D11;'>"
            f"<p style='margin:0; font-size:12px; color:#3B6D11;'>RECOMMENDED PREDICTION</p>"
            f"<p style='margin:10px 0 0 0; font-size:48px; font-weight:bold;'>{final_a}–{final_b}</p>"
            f"<p style='margin:10px 0 0 0; font-size:14px; color:#333;'>{strategy_reason}</p>"
            f"<p style='margin:5px 0 0 0; font-size:14px; color:#3B6D11; font-weight:bold;'>"
            f"Expected Value: {final_ev:.1f} pts</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("---")

    # Three column layout
    col1, col2, col3 = st.columns(3)

    with col1:
        render_odds_card(odds)

    with col2:
        render_injuries_card(selected_match["team_a"], injuries_a)
        st.write("")
        render_injuries_card(selected_match["team_b"], injuries_b)

    with col3:
        render_form_card(selected_match["team_a"], form_a)
        st.write("")
        render_form_card(selected_match["team_b"], form_b)

    st.markdown("---")

    # EV Heatmap
    render_ev_heatmap(score_matrix, (final_a, final_b))

    st.markdown("---")

    # Alternatives
    render_top_alternatives(score_matrix, (final_a, final_b), final_ev)

    st.markdown("---")

    # Upside Scenarios Section
    st.subheader("📈 Upside Scenarios (High-Risk, High-Reward)")
    st.caption("Alternative predictions if you believe in a blowout or upset")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**If Home Team Dominates:**")
        upside_pred = (final_a + 2, final_b)
        if upside_pred[0] <= 5:
            upside_ev = expected_value(upside_pred[0], upside_pred[1], score_matrix)
            delta = upside_ev - final_ev
            st.metric(
                f"{upside_pred[0]}-{upside_pred[1]}",
                f"{upside_ev:.1f} pts",
                f"{delta:+.1f}" if delta < 0 else f"+{delta:.1f}",
            )
            st.caption(f"Risk: {abs(delta):.1f}pts lower, but covers big wins")

    with col2:
        st.write("**If Upset Occurs:**")
        upside_pred = (final_b + 1, final_a + 1)
        if upside_pred[0] <= 5 and upside_pred[1] <= 5:
            upside_ev = expected_value(upside_pred[0], upside_pred[1], score_matrix)
            delta = upside_ev - final_ev
            st.metric(
                f"{upside_pred[0]}-{upside_pred[1]}",
                f"{upside_ev:.1f} pts",
                f"{delta:+.1f}" if delta < 0 else f"+{delta:.1f}",
            )
            st.caption("Risk: unlikely, but big payout if true")

    with col3:
        st.write("**High-Scoring Draw:**")
        upside_pred = (2, 2)
        upside_ev = expected_value(upside_pred[0], upside_pred[1], score_matrix)
        delta = upside_ev - final_ev
        st.metric(
            f"{upside_pred[0]}-{upside_pred[1]}",
            f"{upside_ev:.1f} pts",
            f"{delta:+.1f}" if delta < 0 else f"+{delta:.1f}",
        )
        st.caption("Risk: lower EV, but 200pts if exact or 100 if any draw")

    st.markdown("---")

    # Manual tester
    st.subheader("Manual Score Tester")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.write("Test score:")
    with col2:
        manual_a = st.number_input(
            "Goals A", min_value=0, max_value=9, value=final_a, key="manual_a"
        )
    with col3:
        st.write("–")
    with col4:
        manual_b = st.number_input(
            "Goals B", min_value=0, max_value=9, value=final_b, key="manual_b"
        )
    with col5:
        pass

    manual_ev = expected_value(manual_a, manual_b, score_matrix)
    st.write(f"**EV for {manual_a}-{manual_b}: {manual_ev:.1f} pts**")

    # Cache info
    cache_age = get_cache_age(f"odds_{match_key}")
    if cache_age:
        st.caption(f"Data cached {format_time(cache_age)}")
    else:
        st.caption("Using live/mock data")


if __name__ == "__main__":
    main()
