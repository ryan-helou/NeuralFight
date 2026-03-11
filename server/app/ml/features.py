"""Feature engineering for fight prediction.

Builds feature vectors from historical fight stats with strict temporal ordering
to prevent data leakage. For each fight, only stats from prior fights are used.
"""

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models import Event, Fight, Fighter, RoundStats


class FeatureBuilder:
    """Builds ML-ready feature vectors from the database."""

    # Rolling windows for career stats
    WINDOWS = [3, 5, None]  # last 3, last 5, all fights

    def __init__(self, session: Session):
        self.session = session

    def build_training_set(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Build the full training dataset from all historical fights.

        Returns:
            (features_df, targets_df) where each row is one fight.
        """
        # Load all fights with event dates, ordered chronologically
        fights = self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(Fight.result == "win")  # Only fights with a winner
            .order_by(Event.date)
        ).all()

        rows = []
        targets = []

        for fight, event_date in fights:
            features = self._build_fight_features(fight, event_date)
            if features is None:
                continue

            rows.append(features)

            # Target: did fighter_2 win? (binary: 0 = f1 wins, 1 = f2 wins)
            winner_is_f2 = 1 if fight.winner_id == fight.fighter_2_id else 0

            targets.append({
                "fight_id": fight.id,
                "winner": winner_is_f2,
                "method_category": fight.method_category or "other",
                "finish_round": min(fight.finish_round, 5) if fight.finish_round else 0,
                "is_decision": 1 if fight.method_category == "decision" else 0,
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

    def _build_fight_features(self, fight: Fight, event_date: date) -> dict | None:
        """Compute all features for a fight, using only data before event_date."""
        f1 = self.session.get(Fighter, fight.fighter_1_id)
        f2 = self.session.get(Fighter, fight.fighter_2_id)
        if not f1 or not f2:
            return None

        f1_stats = self._get_fighter_career_stats(f1.id, event_date)
        f2_stats = self._get_fighter_career_stats(f2.id, event_date)

        # Need at least 1 prior fight for each fighter
        if f1_stats["total_fights"] < 1 or f2_stats["total_fights"] < 1:
            return None

        features = {"fight_id": fight.id}

        # Physical attributes
        features["height_diff"] = (f1.height_inches or 70) - (f2.height_inches or 70)
        features["reach_diff"] = (f1.reach_inches or 70) - (f2.reach_inches or 70)

        # Age
        f1_age = _age_at_date(f1.dob, event_date) if f1.dob else 30
        f2_age = _age_at_date(f2.dob, event_date) if f2.dob else 30
        features["age_diff"] = f1_age - f2_age
        features["f1_age"] = f1_age
        features["f2_age"] = f2_age

        # Experience
        features["experience_diff"] = f1_stats["total_fights"] - f2_stats["total_fights"]

        # Stance matchup (one-hot)
        f1_stance = f1.stance or "orthodox"
        f2_stance = f2.stance or "orthodox"
        features["f1_orthodox"] = int(f1_stance == "orthodox")
        features["f1_southpaw"] = int(f1_stance == "southpaw")
        features["f1_switch"] = int(f1_stance == "switch")
        features["f2_orthodox"] = int(f2_stance == "orthodox")
        features["f2_southpaw"] = int(f2_stance == "southpaw")
        features["f2_switch"] = int(f2_stance == "switch")

        # Fight context
        features["is_title_bout"] = int(fight.is_title_bout)
        features["bout_order"] = fight.bout_order or 0

        # Per-fighter rolling stats and differentials
        for window in self.WINDOWS:
            suffix = f"_last{window}" if window else "_career"

            f1_w = self._get_fighter_rolling_stats(f1.id, event_date, window)
            f2_w = self._get_fighter_rolling_stats(f2.id, event_date, window)

            stat_keys = [
                "sig_strikes_per_min", "sig_strike_accuracy", "sig_strikes_absorbed_per_min",
                "sig_strike_defense", "takedowns_per_15min", "takedown_accuracy",
                "takedown_defense", "sub_attempts_per_15min", "control_time_per_15min",
                "knockdown_rate", "finish_rate_ko", "finish_rate_sub", "avg_fight_time_min",
                "win_rate",
            ]

            for key in stat_keys:
                features[f"f1_{key}{suffix}"] = f1_w.get(key, 0)
                features[f"f2_{key}{suffix}"] = f2_w.get(key, 0)
                features[f"{key}_diff{suffix}"] = f1_w.get(key, 0) - f2_w.get(key, 0)

        # Win streak
        features["f1_win_streak"] = f1_stats["win_streak"]
        features["f2_win_streak"] = f2_stats["win_streak"]
        features["win_streak_diff"] = f1_stats["win_streak"] - f2_stats["win_streak"]

        return features

    def _get_fighter_career_stats(self, fighter_id: int, before_date: date) -> dict:
        """Get basic career stats for a fighter before a given date."""
        fights = self.session.execute(
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

        total = len(fights)
        wins = sum(1 for f, _ in fights if f.winner_id == fighter_id)

        # Win streak (consecutive recent wins)
        win_streak = 0
        for f, _ in fights:
            if f.winner_id == fighter_id:
                win_streak += 1
            else:
                break

        return {
            "total_fights": total,
            "wins": wins,
            "win_streak": win_streak,
        }

    def _get_fighter_rolling_stats(
        self, fighter_id: int, before_date: date, window: int | None
    ) -> dict:
        """Compute rolling performance stats for a fighter.

        Args:
            fighter_id: The fighter's database ID.
            before_date: Only use fights before this date.
            window: Number of recent fights to consider, or None for all.
        """
        # Get fights for this fighter before the cutoff date
        query = (
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(
                and_(
                    Event.date < before_date,
                    (Fight.fighter_1_id == fighter_id) | (Fight.fighter_2_id == fighter_id),
                )
            )
            .order_by(Event.date.desc())
        )
        if window:
            query = query.limit(window)

        fights = self.session.execute(query).all()
        if not fights:
            return {}

        # Aggregate round stats across these fights
        fight_ids = [f.id for f, _ in fights]
        round_stats = self.session.execute(
            select(RoundStats).where(
                and_(
                    RoundStats.fight_id.in_(fight_ids),
                    RoundStats.fighter_id == fighter_id,
                )
            )
        ).scalars().all()

        # Also get opponent round stats for defense calculations
        opponent_round_stats = self.session.execute(
            select(RoundStats).where(
                and_(
                    RoundStats.fight_id.in_(fight_ids),
                    RoundStats.fighter_id != fighter_id,
                )
            )
        ).scalars().all()

        # Calculate total fight time in minutes
        total_time_min = 0
        for fight, _ in fights:
            if fight.finish_round and fight.finish_time:
                parts = fight.finish_time.split(":")
                try:
                    mins = int(parts[0])
                    secs = int(parts[1]) if len(parts) > 1 else 0
                    total_time_min += (fight.finish_round - 1) * 5 + mins + secs / 60
                except (ValueError, IndexError):
                    total_time_min += (fight.total_rounds or 3) * 5
            else:
                total_time_min += (fight.total_rounds or 3) * 5

        if total_time_min == 0:
            total_time_min = 1  # Avoid division by zero

        num_fights = len(fights)

        # Aggregate stats
        sig_landed = sum(r.sig_strikes_landed or 0 for r in round_stats)
        sig_attempted = sum(r.sig_strikes_attempted or 0 for r in round_stats)
        opp_sig_landed = sum(r.sig_strikes_landed or 0 for r in opponent_round_stats)
        opp_sig_attempted = sum(r.sig_strikes_attempted or 0 for r in opponent_round_stats)
        td_landed = sum(r.takedowns_landed or 0 for r in round_stats)
        td_attempted = sum(r.takedowns_attempted or 0 for r in round_stats)
        opp_td_landed = sum(r.takedowns_landed or 0 for r in opponent_round_stats)
        opp_td_attempted = sum(r.takedowns_attempted or 0 for r in opponent_round_stats)
        sub_attempts = sum(r.submissions_attempted or 0 for r in round_stats)
        control_seconds = sum(r.control_time_seconds or 0 for r in round_stats)
        knockdowns = sum(r.knockdowns or 0 for r in round_stats)

        # Win method counts
        wins_ko = sum(
            1 for f, _ in fights
            if f.winner_id == fighter_id and f.method_category == "ko_tko"
        )
        wins_sub = sum(
            1 for f, _ in fights
            if f.winner_id == fighter_id and f.method_category == "submission"
        )
        wins = sum(1 for f, _ in fights if f.winner_id == fighter_id)

        return {
            "sig_strikes_per_min": sig_landed / total_time_min,
            "sig_strike_accuracy": sig_landed / max(sig_attempted, 1),
            "sig_strikes_absorbed_per_min": opp_sig_landed / total_time_min,
            "sig_strike_defense": 1 - (opp_sig_landed / max(opp_sig_attempted, 1)),
            "takedowns_per_15min": (td_landed / total_time_min) * 15,
            "takedown_accuracy": td_landed / max(td_attempted, 1),
            "takedown_defense": 1 - (opp_td_landed / max(opp_td_attempted, 1)),
            "sub_attempts_per_15min": (sub_attempts / total_time_min) * 15,
            "control_time_per_15min": (control_seconds / 60) / total_time_min * 15,
            "knockdown_rate": knockdowns / num_fights,
            "finish_rate_ko": wins_ko / max(wins, 1),
            "finish_rate_sub": wins_sub / max(wins, 1),
            "avg_fight_time_min": total_time_min / num_fights,
            "win_rate": wins / num_fights,
        }


def _age_at_date(dob: date, event_date: date) -> float:
    """Calculate age in years at a given date."""
    delta = event_date - dob
    return delta.days / 365.25
