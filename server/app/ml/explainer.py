"""SHAP-based explanation engine for transparent fight predictions."""

import logging

import numpy as np
import pandas as pd
import shap

logger = logging.getLogger(__name__)

# Human-readable feature name translations
FEATURE_TRANSLATIONS = {
    "sig_strikes_per_min_diff": "significant strikes landed per minute",
    "sig_strike_accuracy_diff": "significant strike accuracy",
    "sig_strikes_absorbed_per_min_diff": "significant strikes absorbed per minute",
    "sig_strike_defense_diff": "significant strike defense",
    "takedowns_per_15min_diff": "takedowns landed per 15 minutes",
    "takedown_accuracy_diff": "takedown accuracy",
    "takedown_defense_diff": "takedown defense",
    "sub_attempts_per_15min_diff": "submission attempts per 15 minutes",
    "control_time_per_15min_diff": "control time per 15 minutes",
    "knockdown_rate_diff": "knockdown rate",
    "finish_rate_ko_diff": "KO/TKO finish rate",
    "finish_rate_sub_diff": "submission finish rate",
    "avg_fight_time_min_diff": "average fight duration",
    "win_rate_diff": "win rate",
    "height_diff": "height advantage",
    "reach_diff": "reach advantage",
    "age_diff": "age difference",
    "experience_diff": "experience (total fights)",
    "win_streak_diff": "win streak",
    "avg_opp_win_rate_diff": "opponent quality (strength of schedule)",
    "avg_beaten_opp_win_rate_diff": "quality of wins (beaten opponents' win rate)",
    "avg_lost_to_opp_win_rate_diff": "quality of losses (lost-to opponents' win rate)",
    "best_win_opp_rate_diff": "best win quality",
    "worst_loss_opp_rate_diff": "worst loss quality",
    "avg_opp_win_rate_recent_diff": "recent opponent quality",
    "avg_win_dominance_diff": "win dominance (how decisively they win)",
    "avg_loss_dominance_diff": "loss competitiveness (how close their losses are)",
    "avg_win_dominance_recent_diff": "recent win dominance",
    "avg_loss_dominance_recent_diff": "recent loss competitiveness",
    "finish_speed_diff": "finish speed (how quickly they stop opponents)",
    "been_finished_rate_diff": "been finished rate (KO/sub vulnerability)",
}


class Explainer:
    """Generate human-readable explanations for fight predictions using SHAP."""

    def __init__(self, model, feature_names: list[str]):
        """Initialize with a trained model.

        Args:
            model: CalibratedClassifierCV wrapping a LightGBM model.
            feature_names: List of feature column names.
        """
        self.feature_names = feature_names
        # Extract the base LightGBM model for SHAP
        try:
            self.base_model = model.calibrated_classifiers_[0].estimator
            self.explainer = shap.TreeExplainer(self.base_model)
        except Exception as e:
            logger.warning(f"Could not initialize SHAP explainer: {e}")
            self.explainer = None

    def explain(
        self,
        features: dict,
        fighter_1_name: str,
        fighter_2_name: str,
        f1_win_prob: float,
    ) -> tuple[str, list[dict]]:
        """Generate a rationale and feature importance list for a prediction.

        Args:
            features: Feature dictionary for the fight.
            fighter_1_name: Name of fighter 1.
            fighter_2_name: Name of fighter 2.
            f1_win_prob: Predicted probability that fighter 1 wins.

        Returns:
            (rationale_text, feature_importances)
        """
        if not self.explainer:
            return _fallback_rationale(fighter_1_name, fighter_2_name, f1_win_prob), []

        X = pd.DataFrame([{k: features.get(k, 0) for k in self.feature_names}])
        shap_values = self.explainer.shap_values(X)

        # For binary classification, shap_values may be a list [class_0, class_1]
        if isinstance(shap_values, list):
            sv = shap_values[1][0]  # SHAP values for class 1 (fighter_2 wins)
        else:
            sv = shap_values[0]

        # Build feature importance list sorted by absolute SHAP value
        importances = []
        for i, name in enumerate(self.feature_names):
            importances.append({
                "name": name,
                "shap_value": float(sv[i]),
                "feature_value": float(X.iloc[0, i]),
            })

        importances.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        top_5 = importances[:5]

        # Build rationale
        favored = fighter_1_name if f1_win_prob >= 0.5 else fighter_2_name
        underdog = fighter_2_name if f1_win_prob >= 0.5 else fighter_1_name
        prob = max(f1_win_prob, 1 - f1_win_prob)

        rationale_parts = [
            f"{favored} is favored at {prob:.0%} over {underdog}."
        ]

        reasons = []
        for feat in top_5:
            readable = _translate_feature(feat["name"], feat["feature_value"], fighter_1_name, fighter_2_name)
            if readable:
                reasons.append(readable)

        if reasons:
            rationale_parts.append("Key factors: " + "; ".join(reasons[:3]) + ".")

        rationale = " ".join(rationale_parts)
        return rationale, importances[:10]


def _translate_feature(name: str, value: float, f1_name: str, f2_name: str) -> str | None:
    """Translate a feature name and value into a human-readable statement."""
    # Look for differential features
    for key, desc in FEATURE_TRANSLATIONS.items():
        if key in name:
            if abs(value) < 0.01:
                return None
            better = f1_name if value > 0 else f2_name
            suffix = ""
            # Determine the window
            if "_last3" in name:
                suffix = " (last 3 fights)"
            elif "_last5" in name:
                suffix = " (last 5 fights)"
            elif "_career" in name:
                suffix = " (career)"
            return f"{better} has a {desc} advantage{suffix}"

    return None


def _fallback_rationale(f1_name: str, f2_name: str, f1_win_prob: float) -> str:
    """Generate a basic rationale when SHAP is not available."""
    favored = f1_name if f1_win_prob >= 0.5 else f2_name
    prob = max(f1_win_prob, 1 - f1_win_prob)
    return f"{favored} is favored at {prob:.0%} based on historical fight statistics and matchup analysis."
