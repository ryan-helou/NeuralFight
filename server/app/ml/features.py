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

    def build_training_set(self, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Build the full training dataset from all historical fights.

        Randomly swaps fighter_1/fighter_2 ordering for ~50% of fights during
        feature building to prevent the model from learning positional bias
        (the scraper always stores the winner as fighter_1).

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

    def _build_fight_features(self, fight: Fight, event_date: date, swap: bool = False) -> dict | None:
        """Compute all features for a fight, using only data before event_date.

        Args:
            swap: If True, swap fighter_1 and fighter_2 ordering. Used during
                training to prevent positional bias.
        """
        if swap:
            f1 = self.session.get(Fighter, fight.fighter_2_id)
            f2 = self.session.get(Fighter, fight.fighter_1_id)
        else:
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

        # === Inactivity / layoff ===
        f1_layoff = self._get_layoff_days(f1.id, event_date)
        f2_layoff = self._get_layoff_days(f2.id, event_date)
        features["f1_layoff_days"] = f1_layoff
        features["f2_layoff_days"] = f2_layoff
        features["layoff_diff"] = f1_layoff - f2_layoff
        features["f1_long_layoff"] = int(f1_layoff > 365)  # 1+ year off
        features["f2_long_layoff"] = int(f2_layoff > 365)

        # === Cardio / late-fight performance ===
        f1_cardio = self._get_cardio_stats(f1.id, event_date)
        f2_cardio = self._get_cardio_stats(f2.id, event_date)
        for key in ["strike_dropoff", "late_round_win_rate", "r1_output", "r3_plus_output"]:
            features[f"f1_{key}"] = f1_cardio.get(key, 0)
            features[f"f2_{key}"] = f2_cardio.get(key, 0)
            features[f"{key}_diff"] = f1_cardio.get(key, 0) - f2_cardio.get(key, 0)

        # === Fighter style type ===
        f1_style = self._get_fighter_style(f1.id, event_date)
        f2_style = self._get_fighter_style(f2.id, event_date)
        for key in ["striker_score", "grappler_score", "wrestler_score", "balanced_score"]:
            features[f"f1_{key}"] = f1_style.get(key, 0.25)
            features[f"f2_{key}"] = f2_style.get(key, 0.25)
        # Style matchup interactions
        features["striker_vs_grappler"] = f1_style.get("striker_score", 0) * f2_style.get("grappler_score", 0)
        features["grappler_vs_striker"] = f1_style.get("grappler_score", 0) * f2_style.get("striker_score", 0)
        features["wrestler_vs_striker"] = f1_style.get("wrestler_score", 0) * f2_style.get("striker_score", 0)
        features["striker_vs_wrestler"] = f1_style.get("striker_score", 0) * f2_style.get("wrestler_score", 0)

        # === Weight class movement ===
        f1_wc = self._get_weight_class_movement(f1.id, fight.weight_class, event_date)
        f2_wc = self._get_weight_class_movement(f2.id, fight.weight_class, event_date)
        features["f1_moving_up"] = int(f1_wc.get("direction", 0) > 0)
        features["f1_moving_down"] = int(f1_wc.get("direction", 0) < 0)
        features["f2_moving_up"] = int(f2_wc.get("direction", 0) > 0)
        features["f2_moving_down"] = int(f2_wc.get("direction", 0) < 0)
        features["f1_fights_at_weight"] = f1_wc.get("fights_at_weight", 0)
        features["f2_fights_at_weight"] = f2_wc.get("fights_at_weight", 0)

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

        # === Deep striking patterns ===
        f1_striking = self._get_deep_striking_stats(f1.id, event_date)
        f2_striking = self._get_deep_striking_stats(f2.id, event_date)
        for key in [
            "head_target_pct", "body_target_pct", "leg_target_pct",
            "distance_pct", "clinch_pct", "ground_pct",
            "head_accuracy", "body_accuracy", "leg_accuracy",
            "head_defense", "body_defense", "leg_defense",
            "striking_variety",  # How diverse their attack targets are
            "distance_defense",  # Defense at range specifically
        ]:
            features[f"f1_{key}"] = f1_striking.get(key, 0)
            features[f"f2_{key}"] = f2_striking.get(key, 0)
            features[f"{key}_diff"] = f1_striking.get(key, 0) - f2_striking.get(key, 0)

        # === Chin durability / damage absorption trends ===
        f1_chin = self._get_chin_stats(f1.id, event_date)
        f2_chin = self._get_chin_stats(f2.id, event_date)
        for key in [
            "kd_absorbed_rate", "kd_absorbed_trend",  # Getting knocked down more or less over time
            "damage_absorbed_trend",  # Absorbing more strikes over career (chin fading?)
            "times_knocked_down", "fights_since_last_kd_loss",
            "ko_loss_rate", "sub_loss_rate", "dec_loss_rate",
        ]:
            features[f"f1_{key}"] = f1_chin.get(key, 0)
            features[f"f2_{key}"] = f2_chin.get(key, 0)
            features[f"{key}_diff"] = f1_chin.get(key, 0) - f2_chin.get(key, 0)

        # === Comeback and momentum stats ===
        f1_momentum = self._get_momentum_stats(f1.id, event_date)
        f2_momentum = self._get_momentum_stats(f2.id, event_date)
        for key in [
            "comeback_rate",  # Won fights after losing a round
            "fast_starter",  # R1 finish rate
            "slow_starter",  # Lost R1 on stats but won the fight
            "loss_streak",  # Current consecutive losses
            "career_trajectory",  # Improving or declining (recent vs career win rate)
            "finishing_streak",  # Consecutive finishes
            "ufc_debut",  # Is this their first or second UFC fight?
            "rounds_fought_total",
        ]:
            features[f"f1_{key}"] = f1_momentum.get(key, 0)
            features[f"f2_{key}"] = f2_momentum.get(key, 0)
            features[f"{key}_diff"] = f1_momentum.get(key, 0) - f2_momentum.get(key, 0)

        # === Grappling deep dive ===
        f1_grap = self._get_deep_grappling_stats(f1.id, event_date)
        f2_grap = self._get_deep_grappling_stats(f2.id, event_date)
        for key in [
            "reversal_rate",  # How often they reverse position
            "ground_strike_rate",  # Ground strikes per control minute
            "top_control_pct",  # % of total control time they have (vs opponent)
            "sub_per_td",  # Submission attempts per takedown landed
            "td_defense_after_kd",  # Proxy: TD defense in fights where they got knocked down
            "anti_wrestling",  # Win rate when being out-wrestled (opponent lands more TDs)
        ]:
            features[f"f1_{key}"] = f1_grap.get(key, 0)
            features[f"f2_{key}"] = f2_grap.get(key, 0)
            features[f"{key}_diff"] = f1_grap.get(key, 0) - f2_grap.get(key, 0)

        # === Per-round performance patterns ===
        f1_rounds = self._get_round_patterns(f1.id, event_date)
        f2_rounds = self._get_round_patterns(f2.id, event_date)
        for key in [
            "r1_sig_per_min", "r2_sig_per_min", "r3_sig_per_min",
            "r1_td_rate", "r2_td_rate", "r3_td_rate",
            "r1_kd_rate", "r2_kd_rate", "r3_kd_rate",
            "championship_round_output",  # R4-R5 sig strikes per min
            "championship_round_experience",  # Number of R4+ rounds fought
            "r1_finish_pct",  # % of finishes in R1
            "late_finish_pct",  # % of finishes in R3+
        ]:
            features[f"f1_{key}"] = f1_rounds.get(key, 0)
            features[f"f2_{key}"] = f2_rounds.get(key, 0)
            features[f"{key}_diff"] = f1_rounds.get(key, 0) - f2_rounds.get(key, 0)

        # === Fight pace and volume ===
        f1_pace = self._get_pace_stats(f1.id, event_date)
        f2_pace = self._get_pace_stats(f2.id, event_date)
        for key in [
            "total_strikes_per_min",  # Overall volume
            "fight_pace",  # Combined strikes (both fighters) per min in their fights
            "output_consistency",  # How consistent is their output round to round
            "clinch_time_pct",  # Estimated % of fight in clinch
            "ground_time_pct",  # Estimated % of fight on ground
            "pressure_score",  # High output + forward movement proxy
        ]:
            features[f"f1_{key}"] = f1_pace.get(key, 0)
            features[f"f2_{key}"] = f2_pace.get(key, 0)
            features[f"{key}_diff"] = f1_pace.get(key, 0) - f2_pace.get(key, 0)

        # === Method vulnerability matchup ===
        # How likely each fighter is to lose by each method, crossed with
        # opponent's ability to win by that method
        f1_rolling = self._get_fighter_rolling_stats(f1.id, event_date, None)
        f2_rolling = self._get_fighter_rolling_stats(f2.id, event_date, None)
        # F1's KO power vs F2's KO vulnerability
        features["f1_ko_vs_f2_chin"] = f1_rolling.get("finish_rate_ko", 0) * f2_chin.get("ko_loss_rate", 0)
        features["f2_ko_vs_f1_chin"] = f2_rolling.get("finish_rate_ko", 0) * f1_chin.get("ko_loss_rate", 0)
        # F1's sub game vs F2's sub vulnerability
        features["f1_sub_vs_f2_subdef"] = f1_rolling.get("finish_rate_sub", 0) * f2_chin.get("sub_loss_rate", 0)
        features["f2_sub_vs_f1_subdef"] = f2_rolling.get("finish_rate_sub", 0) * f1_chin.get("sub_loss_rate", 0)
        # Striker vs wrestler matchup specifics
        features["f1_striking_vs_f2_wrestling"] = f1_striking.get("distance_pct", 0) * f2_grap.get("top_control_pct", 0)
        features["f2_striking_vs_f1_wrestling"] = f2_striking.get("distance_pct", 0) * f1_grap.get("top_control_pct", 0)

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

    def _get_deep_striking_stats(self, fighter_id: int, before_date: date) -> dict:
        """Deep striking breakdown: target selection, accuracy by target, variety."""
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
            return {}

        fight_ids = [f.id for f in fights]
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

        if not my_rounds:
            return {}

        # My strikes by target
        head_l = sum(r.head_strikes_landed or 0 for r in my_rounds)
        head_a = sum(r.head_strikes_attempted or 0 for r in my_rounds)
        body_l = sum(r.body_strikes_landed or 0 for r in my_rounds)
        body_a = sum(r.body_strikes_attempted or 0 for r in my_rounds)
        leg_l = sum(r.leg_strikes_landed or 0 for r in my_rounds)
        leg_a = sum(r.leg_strikes_attempted or 0 for r in my_rounds)
        dist_l = sum(r.distance_strikes_landed or 0 for r in my_rounds)
        dist_a = sum(r.distance_strikes_attempted or 0 for r in my_rounds)
        clinch_l = sum(r.clinch_strikes_landed or 0 for r in my_rounds)
        clinch_a = sum(r.clinch_strikes_attempted or 0 for r in my_rounds)
        ground_l = sum(r.ground_strikes_landed or 0 for r in my_rounds)
        ground_a = sum(r.ground_strikes_attempted or 0 for r in my_rounds)

        total_landed = head_l + body_l + leg_l
        total_by_pos = dist_l + clinch_l + ground_l

        # Opponent strikes at me by target (for defense)
        opp_head_l = sum(r.head_strikes_landed or 0 for r in opp_rounds)
        opp_head_a = sum(r.head_strikes_attempted or 0 for r in opp_rounds)
        opp_body_l = sum(r.body_strikes_landed or 0 for r in opp_rounds)
        opp_body_a = sum(r.body_strikes_attempted or 0 for r in opp_rounds)
        opp_leg_l = sum(r.leg_strikes_landed or 0 for r in opp_rounds)
        opp_leg_a = sum(r.leg_strikes_attempted or 0 for r in opp_rounds)
        opp_dist_l = sum(r.distance_strikes_landed or 0 for r in opp_rounds)
        opp_dist_a = sum(r.distance_strikes_attempted or 0 for r in opp_rounds)

        # Striking variety: entropy of target distribution (higher = more diverse)
        probs = []
        if total_landed > 0:
            probs = [head_l / total_landed, body_l / total_landed, leg_l / total_landed]
        variety = -sum(p * np.log(max(p, 1e-10)) for p in probs) / np.log(3) if probs else 0

        return {
            "head_target_pct": head_l / max(total_landed, 1),
            "body_target_pct": body_l / max(total_landed, 1),
            "leg_target_pct": leg_l / max(total_landed, 1),
            "distance_pct": dist_l / max(total_by_pos, 1),
            "clinch_pct": clinch_l / max(total_by_pos, 1),
            "ground_pct": ground_l / max(total_by_pos, 1),
            "head_accuracy": head_l / max(head_a, 1),
            "body_accuracy": body_l / max(body_a, 1),
            "leg_accuracy": leg_l / max(leg_a, 1),
            "head_defense": 1 - (opp_head_l / max(opp_head_a, 1)),
            "body_defense": 1 - (opp_body_l / max(opp_body_a, 1)),
            "leg_defense": 1 - (opp_leg_l / max(opp_leg_a, 1)),
            "striking_variety": variety,
            "distance_defense": 1 - (opp_dist_l / max(opp_dist_a, 1)),
        }

    def _get_chin_stats(self, fighter_id: int, before_date: date) -> dict:
        """Chin durability, damage absorption trends, loss method breakdown."""
        fights = self.session.execute(
            select(Fight, Event.date)
            .join(Event, Fight.event_id == Event.id)
            .where(
                and_(
                    Event.date < before_date,
                    (Fight.fighter_1_id == fighter_id) | (Fight.fighter_2_id == fighter_id),
                )
            )
            .order_by(Event.date)  # Chronological for trend
        ).all()

        if not fights:
            return {}

        total = len(fights)
        losses = [(f, d) for f, d in fights if f.winner_id and f.winner_id != fighter_id]
        ko_losses = sum(1 for f, _ in losses if f.method_category == "ko_tko")
        sub_losses = sum(1 for f, _ in losses if f.method_category == "submission")
        dec_losses = sum(1 for f, _ in losses if f.method_category == "decision")
        total_losses = len(losses)

        # Knockdowns absorbed over career
        fight_ids = [f.id for f, _ in fights]
        opp_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id.in_(fight_ids), RoundStats.fighter_id != fighter_id)
            )
        ).scalars().all()

        # Group KDs by fight for trend analysis
        total_kds = 0
        kds_per_fight = []
        absorbed_per_fight = []

        for fight, _ in fights:
            fight_opp_rounds = [r for r in opp_rounds if r.fight_id == fight.id]
            fight_kds = sum(r.knockdowns or 0 for r in fight_opp_rounds)
            fight_absorbed = sum(r.sig_strikes_landed or 0 for r in fight_opp_rounds)
            total_kds += fight_kds
            kds_per_fight.append(fight_kds)
            absorbed_per_fight.append(fight_absorbed)

        # Trend: compare first half vs second half of career
        if len(kds_per_fight) >= 4:
            mid = len(kds_per_fight) // 2
            early_kd = np.mean(kds_per_fight[:mid])
            late_kd = np.mean(kds_per_fight[mid:])
            kd_trend = late_kd - early_kd  # Positive = getting knocked down more (chin fading)

            early_absorbed = np.mean(absorbed_per_fight[:mid])
            late_absorbed = np.mean(absorbed_per_fight[mid:])
            damage_trend = (late_absorbed - early_absorbed) / max(early_absorbed, 1)
        else:
            kd_trend = 0
            damage_trend = 0

        # Fights since last KO/TKO loss
        fights_since_ko_loss = 0
        for f, _ in reversed(fights):
            if f.winner_id and f.winner_id != fighter_id and f.method_category == "ko_tko":
                break
            fights_since_ko_loss += 1

        return {
            "kd_absorbed_rate": total_kds / max(total, 1),
            "kd_absorbed_trend": kd_trend,
            "damage_absorbed_trend": damage_trend,
            "times_knocked_down": total_kds,
            "fights_since_last_kd_loss": fights_since_ko_loss,
            "ko_loss_rate": ko_losses / max(total_losses, 1),
            "sub_loss_rate": sub_losses / max(total_losses, 1),
            "dec_loss_rate": dec_losses / max(total_losses, 1),
        }

    def _get_momentum_stats(self, fighter_id: int, before_date: date) -> dict:
        """Comeback ability, fast/slow starter, trajectory, streaks."""
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

        total = len(fights)
        wins = sum(1 for f, _ in fights if f.winner_id == fighter_id)

        # Loss streak
        loss_streak = 0
        for f, _ in fights:
            if f.winner_id and f.winner_id != fighter_id:
                loss_streak += 1
            else:
                break

        # Finishing streak (consecutive finishes)
        finishing_streak = 0
        for f, _ in fights:
            if f.winner_id == fighter_id and f.method_category in ("ko_tko", "submission"):
                finishing_streak += 1
            else:
                break

        # Career trajectory: last 3 win rate vs career win rate
        recent_3 = fights[:3]
        recent_wins = sum(1 for f, _ in recent_3 if f.winner_id == fighter_id)
        recent_rate = recent_wins / max(len(recent_3), 1)
        career_rate = wins / max(total, 1)
        trajectory = recent_rate - career_rate  # Positive = improving

        # R1 finish rate (fast starter)
        r1_finishes = sum(
            1 for f, _ in fights
            if f.winner_id == fighter_id and f.finish_round == 1 and f.method_category in ("ko_tko", "submission")
        )

        # Comeback rate: won after losing R1 on stats
        comebacks = 0
        multi_round_wins = 0
        for fight, _ in fights:
            if fight.winner_id != fighter_id:
                continue
            if not fight.finish_round or fight.finish_round < 2:
                continue
            # Check if they were "losing" R1
            r1_stats = self.session.execute(
                select(RoundStats).where(
                    and_(RoundStats.fight_id == fight.id, RoundStats.round_number == 1)
                )
            ).scalars().all()

            my_r1 = [r for r in r1_stats if r.fighter_id == fighter_id]
            opp_r1 = [r for r in r1_stats if r.fighter_id != fighter_id]
            if my_r1 and opp_r1:
                my_sig = my_r1[0].sig_strikes_landed or 0
                opp_sig = opp_r1[0].sig_strikes_landed or 0
                multi_round_wins += 1
                if opp_sig > my_sig:
                    comebacks += 1

        # Slow starter: won fight but got outstruck in R1
        slow_starter = comebacks / max(multi_round_wins, 1)

        # UFC debut flag
        ufc_debut = 1 if total <= 1 else 0

        # Total rounds fought
        rounds_total = sum(
            f.finish_round or f.total_rounds or 3 for f, _ in fights
        )

        return {
            "comeback_rate": comebacks / max(multi_round_wins, 1),
            "fast_starter": r1_finishes / max(wins, 1),
            "slow_starter": slow_starter,
            "loss_streak": loss_streak,
            "career_trajectory": trajectory,
            "finishing_streak": finishing_streak,
            "ufc_debut": ufc_debut,
            "rounds_fought_total": rounds_total,
        }

    def _get_deep_grappling_stats(self, fighter_id: int, before_date: date) -> dict:
        """Deep grappling: reversals, ground work efficiency, anti-wrestling."""
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
            return {}

        fight_ids = [f.id for f in fights]
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

        if not my_rounds:
            return {}

        total_rounds = len(my_rounds)
        my_reversals = sum(r.reversals or 0 for r in my_rounds)
        my_td = sum(r.takedowns_landed or 0 for r in my_rounds)
        my_sub = sum(r.submissions_attempted or 0 for r in my_rounds)
        my_ctrl = sum(r.control_time_seconds or 0 for r in my_rounds)
        my_ground = sum(r.ground_strikes_landed or 0 for r in my_rounds)

        opp_td = sum(r.takedowns_landed or 0 for r in opp_rounds)
        opp_ctrl = sum(r.control_time_seconds or 0 for r in opp_rounds)

        total_ctrl = my_ctrl + opp_ctrl

        # Ground strike rate: strikes per minute of control
        ground_strike_rate = my_ground / max(my_ctrl / 60, 0.1) if my_ctrl > 0 else 0

        # Anti-wrestling: win rate in fights where opponent lands more TDs
        anti_wrestling_wins = 0
        anti_wrestling_total = 0
        for fight in fights:
            fight_my = [r for r in my_rounds if r.fight_id == fight.id]
            fight_opp = [r for r in opp_rounds if r.fight_id == fight.id]
            my_fight_td = sum(r.takedowns_landed or 0 for r in fight_my)
            opp_fight_td = sum(r.takedowns_landed or 0 for r in fight_opp)
            if opp_fight_td > my_fight_td:
                anti_wrestling_total += 1
                if fight.winner_id == fighter_id:
                    anti_wrestling_wins += 1

        return {
            "reversal_rate": my_reversals / max(total_rounds, 1),
            "ground_strike_rate": ground_strike_rate,
            "top_control_pct": my_ctrl / max(total_ctrl, 1),
            "sub_per_td": my_sub / max(my_td, 1),
            "td_defense_after_kd": 0,  # Would need per-sequence data we don't have
            "anti_wrestling": anti_wrestling_wins / max(anti_wrestling_total, 1),
        }

    def _get_round_patterns(self, fighter_id: int, before_date: date) -> dict:
        """Per-round performance breakdown and championship round experience."""
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
            return {}

        fight_ids = [f.id for f in fights]
        my_rounds = self.session.execute(
            select(RoundStats).where(
                and_(RoundStats.fight_id.in_(fight_ids), RoundStats.fighter_id == fighter_id)
            )
        ).scalars().all()

        if not my_rounds:
            return {}

        # Group stats by round number
        round_sig = {}  # {round_num: [sig_strikes_landed, ...]}
        round_td = {}
        round_kd = {}
        for r in my_rounds:
            rn = r.round_number
            round_sig.setdefault(rn, []).append(r.sig_strikes_landed or 0)
            round_td.setdefault(rn, []).append(r.takedowns_landed or 0)
            round_kd.setdefault(rn, []).append(r.knockdowns or 0)

        # 5 min per round assumed
        def avg_per_min(vals):
            return np.mean(vals) / 5 if vals else 0

        # Championship rounds (R4+R5)
        champ_sig = round_sig.get(4, []) + round_sig.get(5, [])
        champ_experience = len(round_sig.get(4, [])) + len(round_sig.get(5, []))

        # Finish distributions
        wins = [f for f in fights if f.winner_id == fighter_id]
        finishes = [f for f in wins if f.method_category in ("ko_tko", "submission")]
        r1_finishes = sum(1 for f in finishes if f.finish_round == 1)
        late_finishes = sum(1 for f in finishes if f.finish_round and f.finish_round >= 3)

        return {
            "r1_sig_per_min": avg_per_min(round_sig.get(1, [])),
            "r2_sig_per_min": avg_per_min(round_sig.get(2, [])),
            "r3_sig_per_min": avg_per_min(round_sig.get(3, [])),
            "r1_td_rate": np.mean(round_td.get(1, [0])),
            "r2_td_rate": np.mean(round_td.get(2, [0])),
            "r3_td_rate": np.mean(round_td.get(3, [0])),
            "r1_kd_rate": np.mean(round_kd.get(1, [0])),
            "r2_kd_rate": np.mean(round_kd.get(2, [0])),
            "r3_kd_rate": np.mean(round_kd.get(3, [0])),
            "championship_round_output": avg_per_min(champ_sig),
            "championship_round_experience": champ_experience,
            "r1_finish_pct": r1_finishes / max(len(finishes), 1),
            "late_finish_pct": late_finishes / max(len(finishes), 1),
        }

    def _get_pace_stats(self, fighter_id: int, before_date: date) -> dict:
        """Fight pace, volume, consistency, and positional breakdown."""
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
            return {}

        fight_ids = [f.id for f in fights]
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

        if not my_rounds:
            return {}

        # Total fight time
        total_time_min = 0
        for fight in fights:
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
        total_time_min = max(total_time_min, 1)

        my_total = sum(r.total_strikes_landed or 0 for r in my_rounds)
        opp_total = sum(r.total_strikes_landed or 0 for r in opp_rounds)
        my_clinch = sum(r.clinch_strikes_landed or 0 for r in my_rounds)
        my_ground = sum(r.ground_strikes_landed or 0 for r in my_rounds)
        my_ctrl = sum(r.control_time_seconds or 0 for r in my_rounds)
        opp_ctrl = sum(r.control_time_seconds or 0 for r in opp_rounds)

        # Per-round output for consistency
        round_outputs = []
        for r in my_rounds:
            round_outputs.append(r.sig_strikes_landed or 0)
        output_std = np.std(round_outputs) if len(round_outputs) > 1 else 0
        output_mean = np.mean(round_outputs) if round_outputs else 0
        consistency = 1 - (output_std / max(output_mean, 1))  # Higher = more consistent

        # Positional time estimates (rough from strike distribution)
        total_strikes = my_clinch + my_ground + sum(r.distance_strikes_landed or 0 for r in my_rounds) + 1
        clinch_time = my_clinch / total_strikes
        ground_time = my_ground / total_strikes + (my_ctrl + opp_ctrl) / max(total_time_min * 60, 1)
        ground_time = min(ground_time, 1.0)

        # Pressure score: high output + forward pressure proxy (landing more than absorbing)
        pressure = (my_total - opp_total) / max(total_time_min, 1)

        return {
            "total_strikes_per_min": my_total / total_time_min,
            "fight_pace": (my_total + opp_total) / total_time_min,
            "output_consistency": max(0, consistency),
            "clinch_time_pct": clinch_time,
            "ground_time_pct": ground_time,
            "pressure_score": pressure,
        }

    def _get_layoff_days(self, fighter_id: int, event_date: date) -> int:
        """Get days since fighter's last fight."""
        last_fight = self.session.execute(
            select(Event.date)
            .join(Fight, Fight.event_id == Event.id)
            .where(
                and_(
                    Event.date < event_date,
                    (Fight.fighter_1_id == fighter_id) | (Fight.fighter_2_id == fighter_id),
                )
            )
            .order_by(Event.date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if last_fight is None:
            return 365  # Default to 1 year if no prior fight
        return (event_date - last_fight).days

    def _get_cardio_stats(self, fighter_id: int, before_date: date) -> dict:
        """Compute cardio / late-fight performance stats.

        Measures strike output drop-off between early and late rounds,
        and win rate in fights that go past round 2.
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
            .limit(10)  # Last 10 fights for cardio analysis
        ).all()

        if not fights:
            return {}

        fight_ids = [f.id for f, _ in fights]

        r1_sig = []  # Sig strikes in round 1
        r3_plus_sig = []  # Sig strikes in rounds 3+
        late_fight_wins = 0
        late_fight_total = 0

        for fight, _ in fights:
            rounds = self.session.execute(
                select(RoundStats).where(
                    and_(
                        RoundStats.fight_id == fight.id,
                        RoundStats.fighter_id == fighter_id,
                    )
                ).order_by(RoundStats.round_number)
            ).scalars().all()

            for r in rounds:
                if r.round_number == 1:
                    r1_sig.append(r.sig_strikes_landed or 0)
                elif r.round_number >= 3:
                    r3_plus_sig.append(r.sig_strikes_landed or 0)

            # Track late-fight (3+ rounds) wins
            total_rounds = fight.total_rounds or fight.finish_round or 3
            if total_rounds >= 3 and fight.finish_round and fight.finish_round >= 3:
                late_fight_total += 1
                if fight.winner_id == fighter_id:
                    late_fight_wins += 1
            elif fight.method_category == "decision":
                late_fight_total += 1
                if fight.winner_id == fighter_id:
                    late_fight_wins += 1

        avg_r1 = np.mean(r1_sig) if r1_sig else 0
        avg_r3 = np.mean(r3_plus_sig) if r3_plus_sig else 0

        # Drop-off: negative = output decreases in later rounds
        dropoff = (avg_r3 - avg_r1) / max(avg_r1, 1) if avg_r1 > 0 else 0

        return {
            "strike_dropoff": dropoff,  # Negative = bad cardio
            "late_round_win_rate": late_fight_wins / max(late_fight_total, 1),
            "r1_output": avg_r1,
            "r3_plus_output": avg_r3,
        }

    def _get_fighter_style(self, fighter_id: int, before_date: date) -> dict:
        """Classify fighter style based on their stat profile.

        Returns scores (0-1) for: striker, grappler, wrestler, balanced.
        Based on how they distribute their offense.
        """
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
            return {"striker_score": 0.25, "grappler_score": 0.25, "wrestler_score": 0.25, "balanced_score": 0.25}

        fight_ids = [f.id for f in fights]
        rounds = self.session.execute(
            select(RoundStats).where(
                and_(
                    RoundStats.fight_id.in_(fight_ids),
                    RoundStats.fighter_id == fighter_id,
                )
            )
        ).scalars().all()

        if not rounds:
            return {"striker_score": 0.25, "grappler_score": 0.25, "wrestler_score": 0.25, "balanced_score": 0.25}

        total_sig = sum(r.sig_strikes_landed or 0 for r in rounds)
        total_distance = sum(r.distance_strikes_landed or 0 for r in rounds)
        total_clinch = sum(r.clinch_strikes_landed or 0 for r in rounds)
        total_ground = sum(r.ground_strikes_landed or 0 for r in rounds)
        total_td = sum(r.takedowns_landed or 0 for r in rounds)
        total_sub = sum(r.submissions_attempted or 0 for r in rounds)
        total_ctrl = sum(r.control_time_seconds or 0 for r in rounds)

        total_actions = total_sig + total_td * 3 + total_sub * 3 + 1  # Weight TDs and subs more

        # Striker: high distance striking, low grappling
        striker_signal = total_distance / max(total_actions, 1)
        # Wrestler: high takedowns and control, moderate ground strikes
        wrestler_signal = (total_td * 3 + total_ctrl / 30) / max(total_actions, 1)
        # Grappler: high submissions and ground work
        grappler_signal = (total_sub * 3 + total_ground + total_ctrl / 60) / max(total_actions, 1)

        # Normalize to sum to 1
        total_signal = striker_signal + wrestler_signal + grappler_signal + 0.01
        striker_score = striker_signal / total_signal
        wrestler_score = wrestler_signal / total_signal
        grappler_score = grappler_signal / total_signal

        # Balanced = how evenly distributed (1 = perfectly balanced)
        scores = [striker_score, wrestler_score, grappler_score]
        balanced_score = 1.0 - np.std(scores) * 3  # Low std = balanced
        balanced_score = max(0, min(1, balanced_score))

        return {
            "striker_score": striker_score,
            "grappler_score": grappler_score,
            "wrestler_score": wrestler_score,
            "balanced_score": balanced_score,
        }

    # Weight class ordering (lighter to heavier)
    WEIGHT_CLASS_ORDER = {
        "Strawweight": 115, "Women's Strawweight": 115,
        "Flyweight": 125, "Women's Flyweight": 125,
        "Bantamweight": 135, "Women's Bantamweight": 135,
        "Featherweight": 145, "Women's Featherweight": 145,
        "Lightweight": 155,
        "Welterweight": 170,
        "Middleweight": 185,
        "Light Heavyweight": 205,
        "Heavyweight": 265,
    }

    def _get_weight_class_movement(self, fighter_id: int, current_weight_class: str | None, before_date: date) -> dict:
        """Detect if a fighter is moving up or down in weight.

        Returns direction (positive = moving up, negative = moving down, 0 = same)
        and number of fights at the current weight class.
        """
        fights = self.session.execute(
            select(Fight)
            .join(Event, Fight.event_id == Event.id)
            .where(
                and_(
                    Event.date < before_date,
                    (Fight.fighter_1_id == fighter_id) | (Fight.fighter_2_id == fighter_id),
                )
            )
            .order_by(Event.date.desc())
        ).scalars().all()

        if not fights or not current_weight_class:
            return {"direction": 0, "fights_at_weight": 0}

        current_weight = self._weight_class_to_lbs(current_weight_class)

        # Count fights at current weight and find most recent different weight
        fights_at_weight = 0
        last_different_weight = None
        for f in fights:
            wc = f.weight_class or ""
            w = self._weight_class_to_lbs(wc)
            if abs(w - current_weight) < 5:  # Same weight class (within 5 lbs)
                fights_at_weight += 1
            elif last_different_weight is None:
                last_different_weight = w

        direction = 0
        if last_different_weight is not None:
            if current_weight > last_different_weight:
                direction = 1  # Moving up
            elif current_weight < last_different_weight:
                direction = -1  # Moving down

        return {"direction": direction, "fights_at_weight": fights_at_weight}

    def _weight_class_to_lbs(self, weight_class: str) -> int:
        """Convert a weight class string to approximate pounds."""
        for name, lbs in self.WEIGHT_CLASS_ORDER.items():
            if name.lower() in weight_class.lower():
                return lbs
        # Try to extract a number from the string
        import re
        match = re.search(r"(\d{3})", weight_class)
        if match:
            return int(match.group(1))
        return 170  # Default to welterweight

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
