"""Lean feature engineering for fight prediction.

~27 carefully selected differential features based on MMA prediction research.
Uses time-decay weighting (1yr half-life), proper MMA Elo (K=200), and
style matchup interactions. Strict temporal ordering prevents data leakage.
"""

from datetime import date
from math import exp, log

import numpy as np
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models import Event, Fight, Fighter, RoundStats


# Weight class ordering for weight class movement detection
WEIGHT_CLASS_ORDER = {
    "Strawweight": 115, "Flyweight": 125, "Bantamweight": 135,
    "Featherweight": 145, "Lightweight": 155, "Welterweight": 170,
    "Middleweight": 185, "Light Heavyweight": 205, "Heavyweight": 265,
    "Women's Strawweight": 115, "Women's Flyweight": 125,
    "Women's Bantamweight": 135, "Women's Featherweight": 145,
}


class FeatureBuilder:
    """Builds ML-ready feature vectors from the database."""

    # Elo system constants
    ELO_DEFAULT = 1500
    ELO_K = 200          # MMA-appropriate K-factor (research: 155-275)
    ELO_K_DEBUT = 275    # Higher K for first 3 fights (more volatile)
    ELO_DEBUT_THRESHOLD = 3

    # Time-decay half-life in days
    DECAY_HALF_LIFE = 365  # 1 year

    def __init__(self, session: Session):
        self.session = session
        # Elo rating system
        self._elo_ratings: dict[int, float] = {}
        self._elo_history: dict[int, list[tuple[date, float]]] = {}
        self._fight_counts: dict[int, int] = {}  # for debut K-factor
        self._elo_computed = False

    def build_training_set(self, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Build the full training dataset from all historical fights.

        Randomly swaps fighter_1/fighter_2 ordering for ~50% of fights during
        feature building to prevent the model from learning positional bias.

        Returns:
            (features_df, targets_df) where each row is one fight.
        """
        import random
        rng = random.Random(seed)

        fights = self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(Fight.result == "win")
            .order_by(Event.date)
        ).all()

        # Precompute Elo ratings chronologically
        self._precompute_elo_ratings()

        rows = []
        targets = []

        for fight, event_date in fights:
            swap = rng.random() < 0.5
            features = self._build_fight_features(fight, event_date, swap=swap)
            if features is None:
                continue

            rows.append(features)

            if swap:
                winner_is_f2 = 1 if fight.winner_id == fight.fighter_1_id else 0
            else:
                winner_is_f2 = 1 if fight.winner_id == fight.fighter_2_id else 0

            targets.append({
                "fight_id": fight.id,
                "winner": winner_is_f2,
                "method_category": fight.method_category or "other",
            })

        features_df = pd.DataFrame(rows)
        targets_df = pd.DataFrame(targets)
        return features_df, targets_df

    def build_fight_features(self, fight_id: int) -> dict | None:
        """Build features for a single fight (for inference)."""
        result = self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(Fight.id == fight_id)
        ).first()
        if not result:
            return None
        fight, event_date = result
        return self._build_fight_features(fight, event_date)

    def _build_fight_features(self, fight: Fight, event_date: date, swap: bool = False) -> dict | None:
        """Compute all features for a fight, using only data before event_date."""
        if swap:
            f1 = self.session.get(Fighter, fight.fighter_2_id)
            f2 = self.session.get(Fighter, fight.fighter_1_id)
        else:
            f1 = self.session.get(Fighter, fight.fighter_1_id)
            f2 = self.session.get(Fighter, fight.fighter_2_id)
        if not f1 or not f2:
            return None

        f1_fights = self._get_prior_fights(f1.id, event_date)
        f2_fights = self._get_prior_fights(f2.id, event_date)

        # Need at least 1 prior fight for each fighter
        if len(f1_fights) < 1 or len(f2_fights) < 1:
            return None

        features: dict = {"fight_id": fight.id}

        # === 1. Elo diff ===
        if not self._elo_computed:
            self._precompute_elo_ratings()
        f1_elo = self._get_elo_at_date(f1.id, event_date)
        f2_elo = self._get_elo_at_date(f2.id, event_date)
        features["elo_diff"] = f1_elo - f2_elo

        # === 2-11. Time-decay weighted stat differentials (1yr half-life) ===
        f1_decay = self._get_time_decay_stats(f1.id, event_date, f1_fights)
        f2_decay = self._get_time_decay_stats(f2.id, event_date, f2_fights)
        for key in [
            "sig_per_min", "sig_accuracy", "sig_absorbed_per_min",
            "sig_defense", "td_per_15min", "td_accuracy",
            "td_defense", "win_rate", "finish_rate", "control_per_15min",
        ]:
            features[f"{key}_diff"] = f1_decay.get(key, 0) - f2_decay.get(key, 0)

        # === 12-16. Basic differentials ===
        features["win_streak_diff"] = self._get_win_streak(f1.id, f1_fights) - self._get_win_streak(f2.id, f2_fights)
        features["experience_diff"] = len(f1_fights) - len(f2_fights)
        f1_age = _age_at_date(f1.dob, event_date) if f1.dob else 30
        f2_age = _age_at_date(f2.dob, event_date) if f2.dob else 30
        features["age_diff"] = f1_age - f2_age
        features["height_diff"] = (f1.height_inches or 70) - (f2.height_inches or 70)
        features["reach_diff"] = (f1.reach_inches or 70) - (f2.reach_inches or 70)

        # === 17. Title bout ===
        features["is_title_bout"] = int(fight.is_title_bout)

        # === 18. Career trajectory diff ===
        features["career_trajectory_diff"] = (
            self._get_career_trajectory(f1.id, f1_fights) -
            self._get_career_trajectory(f2.id, f2_fights)
        )

        # === 19-22. Style matchup interactions ===
        f1_style = self._get_fighter_style(f1.id, f1_fights)
        f2_style = self._get_fighter_style(f2.id, f2_fights)
        features["striker_vs_grappler"] = f1_style["striker"] * f2_style["grappler"]
        features["grappler_vs_striker"] = f1_style["grappler"] * f2_style["striker"]
        features["wrestler_vs_striker"] = f1_style["wrestler"] * f2_style["striker"]
        features["striker_vs_wrestler"] = f1_style["striker"] * f2_style["wrestler"]

        # === 23-24. Head-to-head ===
        h2h = self._get_head_to_head(f1.id, f2.id, event_date)
        features["has_fought_before"] = h2h["has_fought_before"]
        features["h2h_win_diff"] = h2h["win_diff"]

        # === 25. Common opponent win rate diff ===
        features["common_opp_win_rate_diff"] = self._get_common_opp_diff(f1.id, f2.id, event_date)

        # === 26. Output resilience diff ===
        features["output_resilience_diff"] = (
            self._get_output_resilience(f1.id, f1_fights) -
            self._get_output_resilience(f2.id, f2_fights)
        )

        # === 27. Cage size (small octagon = APEX) ===
        event = self.session.execute(
            select(Event).where(Event.id == fight.event_id)
        ).scalar_one_or_none()
        features["small_cage"] = int(_is_small_cage(event)) if event else 0

        return features

    # ----------------------------------------------------------------
    # Helper methods
    # ----------------------------------------------------------------

    def _get_prior_fights(self, fighter_id: int, before_date: date) -> list[tuple[Fight, date]]:
        """Get all fights for a fighter before a given date, newest first."""
        return self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(
                and_(
                    Event.date < before_date,
                    (Fight.fighter_1_id == fighter_id) | (Fight.fighter_2_id == fighter_id),
                )
            )
            .order_by(Event.date.desc())
        ).all()

    def _get_win_streak(self, fighter_id: int, fights: list[tuple[Fight, date]]) -> int:
        """Count consecutive recent wins."""
        streak = 0
        for f, _ in fights:
            if f.winner_id == fighter_id:
                streak += 1
            else:
                break
        return streak

    def _get_career_trajectory(self, fighter_id: int, fights: list[tuple[Fight, date]]) -> float:
        """Recent (last 3) win rate minus career win rate. Positive = improving."""
        if not fights:
            return 0.0
        total = len(fights)
        wins = sum(1 for f, _ in fights if f.winner_id == fighter_id)
        recent = fights[:3]
        recent_wins = sum(1 for f, _ in recent if f.winner_id == fighter_id)
        return (recent_wins / max(len(recent), 1)) - (wins / max(total, 1))

    # --- Elo System ---

    def _precompute_elo_ratings(self):
        """Compute Elo ratings chronologically for all fighters."""
        if self._elo_computed:
            return

        all_fights = self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(Fight.result == "win")
            .order_by(Event.date)
        ).all()

        for fight, event_date in all_fights:
            f1_id = fight.fighter_1_id
            f2_id = fight.fighter_2_id

            # Get current ratings
            r1 = self._elo_ratings.get(f1_id, self.ELO_DEFAULT)
            r2 = self._elo_ratings.get(f2_id, self.ELO_DEFAULT)

            # Record pre-fight ratings
            self._elo_history.setdefault(f1_id, []).append((event_date, r1))
            self._elo_history.setdefault(f2_id, []).append((event_date, r2))

            # Determine K-factor based on fight count
            f1_count = self._fight_counts.get(f1_id, 0)
            f2_count = self._fight_counts.get(f2_id, 0)
            k1 = self.ELO_K_DEBUT if f1_count < self.ELO_DEBUT_THRESHOLD else self.ELO_K
            k2 = self.ELO_K_DEBUT if f2_count < self.ELO_DEBUT_THRESHOLD else self.ELO_K

            # Expected scores
            e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
            e2 = 1 - e1

            # Actual scores (fighter_1 is always the winner in our data since we filter result="win")
            # But we need to check winner_id
            if fight.winner_id == f1_id:
                s1, s2 = 1.0, 0.0
            elif fight.winner_id == f2_id:
                s1, s2 = 0.0, 1.0
            else:
                s1, s2 = 0.5, 0.5  # draw

            # Margin of victory adjustment
            mov = self._margin_of_victory(fight)

            # Update ratings
            self._elo_ratings[f1_id] = r1 + k1 * mov * (s1 - e1)
            self._elo_ratings[f2_id] = r2 + k2 * mov * (s2 - e2)

            # Increment fight counts
            self._fight_counts[f1_id] = f1_count + 1
            self._fight_counts[f2_id] = f2_count + 1

        self._elo_computed = True

    def _margin_of_victory(self, fight: Fight) -> float:
        """MoV multiplier: finishes > decisions, early finishes > late ones."""
        if fight.method_category in ("ko_tko", "submission"):
            # Earlier finish = bigger multiplier
            rd = fight.finish_round or 3
            return 1.0 + (0.4 / rd)  # R1 finish: 1.4x, R3: 1.13x
        return 1.0  # Decision = base multiplier

    def _get_elo_at_date(self, fighter_id: int, event_date: date) -> float:
        """Get a fighter's Elo rating just before a given date."""
        history = self._elo_history.get(fighter_id, [])
        rating = self.ELO_DEFAULT
        for d, r in history:
            if d < event_date:
                rating = r
            else:
                break
        return rating

    # --- Time-Decay Stats ---

    def _get_time_decay_stats(
        self, fighter_id: int, event_date: date, fights: list[tuple[Fight, date]]
    ) -> dict:
        """Compute exponentially weighted stats with 1yr half-life."""
        if not fights:
            return {}

        fight_ids = [f.id for f, _ in fights]
        my_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id.in_(fight_ids), RoundStats.fighter_id == fighter_id)
            )
        ).scalars().all()
        opp_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id.in_(fight_ids), RoundStats.fighter_id != fighter_id)
            )
        ).scalars().all()

        # Group round stats by fight
        my_by_fight = {}
        for r in my_rounds:
            my_by_fight.setdefault(r.fight_id, []).append(r)
        opp_by_fight = {}
        for r in opp_rounds:
            opp_by_fight.setdefault(r.fight_id, []).append(r)

        decay_constant = log(2) / self.DECAY_HALF_LIFE

        # Accumulate weighted stats
        w_total = 0.0
        w_sig_landed = 0.0
        w_sig_attempted = 0.0
        w_opp_sig_landed = 0.0
        w_opp_sig_attempted = 0.0
        w_td_landed = 0.0
        w_td_attempted = 0.0
        w_opp_td_landed = 0.0
        w_opp_td_attempted = 0.0
        w_control_sec = 0.0
        w_time_min = 0.0
        w_wins = 0.0
        w_finishes = 0.0
        w_fights = 0.0

        for fight, fight_date in fights:
            days_ago = (event_date - fight_date).days
            weight = exp(-decay_constant * days_ago)

            my_rs = my_by_fight.get(fight.id, [])
            opp_rs = opp_by_fight.get(fight.id, [])

            fight_time = _get_fight_time_min(fight)

            w_total += weight
            w_time_min += weight * fight_time
            w_fights += weight

            w_sig_landed += weight * sum(r.sig_strikes_landed or 0 for r in my_rs)
            w_sig_attempted += weight * sum(r.sig_strikes_attempted or 0 for r in my_rs)
            w_opp_sig_landed += weight * sum(r.sig_strikes_landed or 0 for r in opp_rs)
            w_opp_sig_attempted += weight * sum(r.sig_strikes_attempted or 0 for r in opp_rs)
            w_td_landed += weight * sum(r.takedowns_landed or 0 for r in my_rs)
            w_td_attempted += weight * sum(r.takedowns_attempted or 0 for r in my_rs)
            w_opp_td_landed += weight * sum(r.takedowns_landed or 0 for r in opp_rs)
            w_opp_td_attempted += weight * sum(r.takedowns_attempted or 0 for r in opp_rs)
            w_control_sec += weight * sum(r.control_time_seconds or 0 for r in my_rs)

            if fight.winner_id == fighter_id:
                w_wins += weight
                if fight.method_category in ("ko_tko", "submission"):
                    w_finishes += weight

        if w_total == 0:
            return {}

        w_time = max(w_time_min, 0.1)

        return {
            "sig_per_min": w_sig_landed / w_time,
            "sig_accuracy": w_sig_landed / max(w_sig_attempted, 1),
            "sig_absorbed_per_min": w_opp_sig_landed / w_time,
            "sig_defense": 1 - (w_opp_sig_landed / max(w_opp_sig_attempted, 1)),
            "td_per_15min": (w_td_landed / w_time) * 15,
            "td_accuracy": w_td_landed / max(w_td_attempted, 1),
            "td_defense": 1 - (w_opp_td_landed / max(w_opp_td_attempted, 1)),
            "win_rate": w_wins / w_fights,
            "finish_rate": w_finishes / max(w_wins, 0.1),
            "control_per_15min": (w_control_sec / 60) / w_time * 15,
        }

    # --- Fighter Style ---

    def _get_fighter_style(self, fighter_id: int, fights: list[tuple[Fight, date]]) -> dict:
        """Classify fighter style based on career stats. Returns scores 0-1."""
        if not fights:
            return {"striker": 0.33, "grappler": 0.33, "wrestler": 0.33}

        fight_ids = [f.id for f, _ in fights]
        my_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id.in_(fight_ids), RoundStats.fighter_id == fighter_id)
            )
        ).scalars().all()

        if not my_rounds:
            return {"striker": 0.33, "grappler": 0.33, "wrestler": 0.33}

        total_time = sum(_get_fight_time_min(f) for f, _ in fights)
        total_time = max(total_time, 0.1)

        sig_per_min = sum(r.sig_strikes_landed or 0 for r in my_rounds) / total_time
        td_per_min = sum(r.takedowns_landed or 0 for r in my_rounds) / total_time
        sub_per_min = sum(r.submissions_attempted or 0 for r in my_rounds) / total_time
        ctrl_per_min = sum(r.control_time_seconds or 0 for r in my_rounds) / 60 / total_time

        # Normalize to scores
        striker = sig_per_min / (sig_per_min + td_per_min * 5 + sub_per_min * 3 + ctrl_per_min * 2 + 0.01)
        wrestler = (td_per_min * 5 + ctrl_per_min * 2) / (sig_per_min + td_per_min * 5 + sub_per_min * 3 + ctrl_per_min * 2 + 0.01)
        grappler = (sub_per_min * 3) / (sig_per_min + td_per_min * 5 + sub_per_min * 3 + ctrl_per_min * 2 + 0.01)

        return {"striker": striker, "grappler": grappler, "wrestler": wrestler}

    # --- Head-to-Head ---

    def _get_head_to_head(self, f1_id: int, f2_id: int, before_date: date) -> dict:
        """Get head-to-head history between two fighters."""
        fights = self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(
                and_(
                    Event.date < before_date,
                    (
                        (Fight.fighter_1_id == f1_id) & (Fight.fighter_2_id == f2_id) |
                        (Fight.fighter_1_id == f2_id) & (Fight.fighter_2_id == f1_id)
                    ),
                )
            )
        ).all()

        if not fights:
            return {"has_fought_before": 0, "win_diff": 0}

        f1_wins = sum(1 for f, _ in fights if f.winner_id == f1_id)
        f2_wins = sum(1 for f, _ in fights if f.winner_id == f2_id)

        return {
            "has_fought_before": 1,
            "win_diff": f1_wins - f2_wins,
        }

    # --- Common Opponents ---

    def _get_common_opp_diff(self, f1_id: int, f2_id: int, before_date: date) -> float:
        """Win rate difference against common opponents."""
        f1_opps = self._get_opponent_results(f1_id, before_date)
        f2_opps = self._get_opponent_results(f2_id, before_date)

        common = set(f1_opps.keys()) & set(f2_opps.keys())
        if not common:
            return 0.0

        f1_wins = sum(f1_opps[opp] for opp in common)
        f2_wins = sum(f2_opps[opp] for opp in common)
        n = len(common)
        return (f1_wins / n) - (f2_wins / n)

    def _get_opponent_results(self, fighter_id: int, before_date: date) -> dict[int, float]:
        """Get win/loss (1.0/0.0) against each opponent before a date."""
        fights = self.session.execute(
            select(Fight)
            .join(Event, Fight.event_id == Event.id)
            .where(
                and_(
                    Event.date < before_date,
                    (Fight.fighter_1_id == fighter_id) | (Fight.fighter_2_id == fighter_id),
                )
            )
        ).scalars().all()

        results: dict[int, float] = {}
        for fight in fights:
            opp_id = fight.fighter_2_id if fight.fighter_1_id == fighter_id else fight.fighter_1_id
            results[opp_id] = 1.0 if fight.winner_id == fighter_id else 0.0
        return results

    # --- Output Resilience ---

    def _get_output_resilience(self, fighter_id: int, fights: list[tuple[Fight, date]]) -> float:
        """Ratio of striking output in losses vs wins. Higher = more resilient under pressure."""
        if not fights:
            return 0.0

        fight_ids = [f.id for f, _ in fights]
        my_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id.in_(fight_ids), RoundStats.fighter_id == fighter_id)
            )
        ).scalars().all()

        my_by_fight = {}
        for r in my_rounds:
            my_by_fight.setdefault(r.fight_id, []).append(r)

        win_output = []
        loss_output = []

        for fight, _ in fights:
            rs = my_by_fight.get(fight.id, [])
            if not rs:
                continue
            fight_time = max(_get_fight_time_min(fight), 0.1)
            sig_per_min = sum(r.sig_strikes_landed or 0 for r in rs) / fight_time

            if fight.winner_id == fighter_id:
                win_output.append(sig_per_min)
            else:
                loss_output.append(sig_per_min)

        if not win_output or not loss_output:
            return 1.0  # No data to compare

        avg_win = np.mean(win_output)
        avg_loss = np.mean(loss_output)
        return avg_loss / max(avg_win, 0.1)


# ----------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------

def _age_at_date(dob: date, event_date: date) -> float:
    """Calculate age in years at a given date."""
    delta = event_date - dob
    return delta.days / 365.25


def _get_fight_time_min(fight: Fight) -> float:
    """Calculate total fight time in minutes."""
    if fight.finish_round and fight.finish_time:
        parts = fight.finish_time.split(":")
        try:
            mins = int(parts[0])
            secs = int(parts[1]) if len(parts) > 1 else 0
            return (fight.finish_round - 1) * 5 + mins + secs / 60
        except (ValueError, IndexError):
            pass
    return (fight.total_rounds or 3) * 5


def _is_small_cage(event: Event) -> bool:
    """Detect if event used the small (25ft) octagon.

    UFC APEX in Las Vegas uses the 25ft octagon.
    All other venues use the standard 30ft octagon.
    """
    name = (event.name or "").lower()
    location = (event.location or "").lower()
    return "apex" in name or "apex" in location
