"""Feature engineering for fight prediction.

Builds feature vectors from historical fight stats with strict temporal ordering
to prevent data leakage. For each fight, only stats from prior fights are used.

Key feature groups:
- Physical attributes (height, reach, age)
- Rolling performance stats (strikes, takedowns, control, etc.)
- Opponent quality / strength of schedule
- Win dominance scores (how decisively fights were won/lost)
- Win streak and experience
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
        # Cache for opponent win rates to avoid repeated queries
        self._win_rate_cache = {}

    def build_training_set(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Build the full training dataset from all historical fights.

        Returns:
            (features_df, targets_df) where each row is one fight.
        """
        fights = self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(Fight.result == "win")
            .order_by(Event.date)
        ).all()

        rows = []
        targets = []

        for fight, event_date in fights:
            features = self._build_fight_features(fight, event_date)
            if features is None:
                continue

            rows.append(features)

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

        # === Physical attributes ===
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

        # === Rolling performance stats ===
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

        # === Win streak ===
        features["f1_win_streak"] = f1_stats["win_streak"]
        features["f2_win_streak"] = f2_stats["win_streak"]
        features["win_streak_diff"] = f1_stats["win_streak"] - f2_stats["win_streak"]

        # === Opponent quality / strength of schedule ===
        f1_opp = self._get_opponent_quality(f1.id, event_date)
        f2_opp = self._get_opponent_quality(f2.id, event_date)

        for key in [
            "avg_opp_win_rate", "avg_beaten_opp_win_rate", "avg_lost_to_opp_win_rate",
            "best_win_opp_rate", "worst_loss_opp_rate",
            "avg_opp_win_rate_recent",
        ]:
            features[f"f1_{key}"] = f1_opp.get(key, 0.5)
            features[f"f2_{key}"] = f2_opp.get(key, 0.5)
            features[f"{key}_diff"] = f1_opp.get(key, 0.5) - f2_opp.get(key, 0.5)

        # === Win dominance scores ===
        f1_dom = self._get_dominance_stats(f1.id, event_date)
        f2_dom = self._get_dominance_stats(f2.id, event_date)

        for key in [
            "avg_win_dominance", "avg_loss_dominance",
            "avg_win_dominance_recent", "avg_loss_dominance_recent",
            "finish_speed", "been_finished_rate",
        ]:
            features[f"f1_{key}"] = f1_dom.get(key, 0)
            features[f"f2_{key}"] = f2_dom.get(key, 0)
            features[f"{key}_diff"] = f1_dom.get(key, 0) - f2_dom.get(key, 0)

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
        """Compute rolling performance stats for a fighter."""
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

        fight_ids = [f.id for f, _ in fights]
        round_stats = self.session.execute(
            select(RoundStats).where(
                and_(
                    RoundStats.fight_id.in_(fight_ids),
                    RoundStats.fighter_id == fighter_id,
                )
            )
        ).scalars().all()

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
            total_time_min = 1

        num_fights = len(fights)

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

    def _get_opponent_quality(self, fighter_id: int, before_date: date) -> dict:
        """Compute opponent quality metrics (strength of schedule).

        Measures: who did this fighter beat, and how good were those opponents?
        Who did they lose to, and how good were those opponents?
        """
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

        if not fights:
            return {}

        all_opp_rates = []
        beaten_opp_rates = []
        lost_to_opp_rates = []

        for fight, fight_date in fights:
            # Identify opponent
            opp_id = fight.fighter_2_id if fight.fighter_1_id == fighter_id else fight.fighter_1_id

            # Get opponent's win rate at the time of this fight
            opp_rate = self._get_win_rate_cached(opp_id, fight_date)
            all_opp_rates.append(opp_rate)

            if fight.winner_id == fighter_id:
                beaten_opp_rates.append(opp_rate)
            elif fight.winner_id == opp_id:
                lost_to_opp_rates.append(opp_rate)

        # Recent = last 3 fights
        recent_opp_rates = all_opp_rates[:3]

        return {
            # Average win rate of all opponents faced
            "avg_opp_win_rate": np.mean(all_opp_rates) if all_opp_rates else 0.5,
            # Average win rate of opponents they beat (quality of wins)
            "avg_beaten_opp_win_rate": np.mean(beaten_opp_rates) if beaten_opp_rates else 0.5,
            # Average win rate of opponents they lost to (quality of losses)
            "avg_lost_to_opp_win_rate": np.mean(lost_to_opp_rates) if lost_to_opp_rates else 0.5,
            # Best win (highest win-rate opponent beaten)
            "best_win_opp_rate": max(beaten_opp_rates) if beaten_opp_rates else 0.5,
            # Worst loss (lowest win-rate opponent lost to)
            "worst_loss_opp_rate": min(lost_to_opp_rates) if lost_to_opp_rates else 0.5,
            # Recent opponent quality (last 3 fights)
            "avg_opp_win_rate_recent": np.mean(recent_opp_rates) if recent_opp_rates else 0.5,
        }

    def _get_win_rate_cached(self, fighter_id: int, before_date: date) -> float:
        """Get a fighter's win rate before a date, with caching."""
        cache_key = (fighter_id, before_date)
        if cache_key in self._win_rate_cache:
            return self._win_rate_cache[cache_key]

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

        if not fights:
            rate = 0.5  # No data, assume average
        else:
            wins = sum(1 for f in fights if f.winner_id == fighter_id)
            rate = wins / len(fights)

        self._win_rate_cache[cache_key] = rate
        return rate

    def _get_dominance_stats(self, fighter_id: int, before_date: date) -> dict:
        """Compute win/loss dominance metrics.

        Measures how decisively a fighter wins or loses, using round stats
        as a proxy for scorecards.

        Dominance score per fight (0-1 scale):
        - Sig strike differential ratio
        - Takedown differential ratio
        - Control time share
        - Knockdown advantage
        - Finish bonus (KO/sub in early round = very dominant)
        """
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

        if not fights:
            return {}

        win_dominance_scores = []
        loss_dominance_scores = []
        finish_rounds = []  # How quickly they finish opponents
        been_finished = 0
        total_fights = len(fights)

        for fight, _ in fights:
            opp_id = fight.fighter_2_id if fight.fighter_1_id == fighter_id else fight.fighter_1_id
            dominance = self._compute_fight_dominance(fight.id, fighter_id, opp_id)

            if fight.winner_id == fighter_id:
                win_dominance_scores.append(dominance)
                # Track how fast they finish people
                if fight.method_category in ("ko_tko", "submission") and fight.finish_round:
                    max_rounds = fight.total_rounds or 3
                    # Earlier finish = higher score. R1 of 3-rounder = 1.0, R3 = 0.33
                    finish_rounds.append(1.0 - (fight.finish_round - 1) / max_rounds)
            elif fight.winner_id == opp_id:
                loss_dominance_scores.append(dominance)
                if fight.method_category in ("ko_tko", "submission"):
                    been_finished += 1

        # Recent = last 3 fights
        recent_wins = [s for i, (f, _) in enumerate(fights[:3])
                       for s in [self._compute_fight_dominance(
                           f.id, fighter_id,
                           f.fighter_2_id if f.fighter_1_id == fighter_id else f.fighter_1_id
                       )] if f.winner_id == fighter_id]
        recent_losses = [s for i, (f, _) in enumerate(fights[:3])
                         for s in [self._compute_fight_dominance(
                             f.id, fighter_id,
                             f.fighter_2_id if f.fighter_1_id == fighter_id else f.fighter_1_id
                         )] if f.winner_id and f.winner_id != fighter_id]

        return {
            # How dominant their wins are (0-1, higher = more dominant)
            "avg_win_dominance": np.mean(win_dominance_scores) if win_dominance_scores else 0.5,
            # How badly they lose (0-1, higher = they performed better even in loss)
            "avg_loss_dominance": np.mean(loss_dominance_scores) if loss_dominance_scores else 0.5,
            # Recent dominance (last 3 fights)
            "avg_win_dominance_recent": np.mean(recent_wins) if recent_wins else 0.5,
            "avg_loss_dominance_recent": np.mean(recent_losses) if recent_losses else 0.5,
            # How fast they finish opponents (0 = never finishes, 1 = always R1 finish)
            "finish_speed": np.mean(finish_rounds) if finish_rounds else 0,
            # How often they get finished (KO/sub'd)
            "been_finished_rate": been_finished / max(total_fights - sum(1 for f, _ in fights if f.winner_id == fighter_id), 1),
        }

    def _compute_fight_dominance(self, fight_id: int, fighter_id: int, opp_id: int) -> float:
        """Compute a dominance score for a single fight (0-1 scale).

        Uses sig strike differential, takedown differential, control time share,
        and knockdowns to estimate how one-sided the fight was.
        """
        fighter_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id == fight_id, RoundStats.fighter_id == fighter_id)
            )
        ).scalars().all()

        opp_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id == fight_id, RoundStats.fighter_id == opp_id)
            )
        ).scalars().all()

        if not fighter_rounds or not opp_rounds:
            return 0.5  # No data, neutral

        # Sig strikes
        f_sig = sum(r.sig_strikes_landed or 0 for r in fighter_rounds)
        o_sig = sum(r.sig_strikes_landed or 0 for r in opp_rounds)
        total_sig = f_sig + o_sig
        sig_share = f_sig / max(total_sig, 1)  # 0-1, 0.5 = even

        # Takedowns
        f_td = sum(r.takedowns_landed or 0 for r in fighter_rounds)
        o_td = sum(r.takedowns_landed or 0 for r in opp_rounds)
        total_td = f_td + o_td
        td_share = f_td / max(total_td, 1) if total_td > 0 else 0.5

        # Control time
        f_ctrl = sum(r.control_time_seconds or 0 for r in fighter_rounds)
        o_ctrl = sum(r.control_time_seconds or 0 for r in opp_rounds)
        total_ctrl = f_ctrl + o_ctrl
        ctrl_share = f_ctrl / max(total_ctrl, 1) if total_ctrl > 0 else 0.5

        # Knockdowns
        f_kd = sum(r.knockdowns or 0 for r in fighter_rounds)
        o_kd = sum(r.knockdowns or 0 for r in opp_rounds)
        kd_advantage = min(1.0, (f_kd - o_kd + 3) / 6)  # Normalize: -3 to +3 -> 0 to 1

        # Weighted combination
        dominance = (
            0.35 * sig_share +       # Striking is the biggest factor
            0.20 * td_share +         # Takedowns matter
            0.25 * ctrl_share +       # Control time (grappling dominance)
            0.20 * kd_advantage       # Knockdowns (fight-ending moments)
        )

        return dominance


def _age_at_date(dob: date, event_date: date) -> float:
    """Calculate age in years at a given date."""
    delta = event_date - dob
    return delta.days / 365.25
