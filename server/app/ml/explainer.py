"""SHAP-based explanation engine for transparent fight predictions."""

import logging

import numpy as np
import pandas as pd
import shap

logger = logging.getLogger(__name__)

# Human-readable category groupings
CATEGORY_MAP = {
    "striking": [
        "sig_strikes_per_min", "sig_strike_accuracy", "sig_strikes_absorbed_per_min",
        "sig_strike_defense", "knockdown_rate", "r1_output", "r3_plus_output",
    ],
    "grappling": [
        "takedowns_per_15min", "takedown_accuracy", "takedown_defense",
        "sub_attempts_per_15min", "control_time_per_15min",
    ],
    "finishing": [
        "finish_rate_ko", "finish_rate_sub", "finish_speed", "been_finished_rate",
    ],
    "experience": [
        "experience", "win_rate", "win_streak", "avg_fight_time_min",
    ],
    "opponent_quality": [
        "avg_opp_win_rate", "avg_beaten_opp_win_rate", "avg_lost_to_opp_win_rate",
        "best_win_opp_rate", "worst_loss_opp_rate", "avg_opp_win_rate_recent",
    ],
    "dominance": [
        "avg_win_dominance", "avg_loss_dominance", "avg_win_dominance_recent",
        "avg_loss_dominance_recent",
    ],
    "physical": [
        "height", "reach", "age",
    ],
    "conditioning": [
        "layoff", "strike_dropoff", "late_round_win_rate",
    ],
}

# Feature descriptions for detailed explanations
FEATURE_DESC = {
    "sig_strikes_per_min_diff": ("significant strikes per minute", "{:.1f}"),
    "sig_strike_accuracy_diff": ("striking accuracy", "{:.0%}"),
    "sig_strikes_absorbed_per_min_diff": ("strikes absorbed per minute", "{:.1f}"),
    "sig_strike_defense_diff": ("strike defense", "{:.0%}"),
    "takedowns_per_15min_diff": ("takedowns per 15 min", "{:.1f}"),
    "takedown_accuracy_diff": ("takedown accuracy", "{:.0%}"),
    "takedown_defense_diff": ("takedown defense", "{:.0%}"),
    "sub_attempts_per_15min_diff": ("submission attempts per 15 min", "{:.1f}"),
    "control_time_per_15min_diff": ("control time per 15 min", "{:.0f}s"),
    "knockdown_rate_diff": ("knockdown rate", "{:.1%}"),
    "finish_rate_ko_diff": ("KO/TKO finish rate", "{:.0%}"),
    "finish_rate_sub_diff": ("submission finish rate", "{:.0%}"),
    "avg_fight_time_min_diff": ("avg fight duration", "{:.1f} min"),
    "win_rate_diff": ("win rate", "{:.0%}"),
    "height_diff": ("height", "{:.0f}\""),
    "reach_diff": ("reach", "{:.0f}\""),
    "age_diff": ("age", "{:.0f} yrs"),
    "experience_diff": ("UFC fights", "{:.0f}"),
    "win_streak_diff": ("win streak", "{:.0f}"),
    "avg_opp_win_rate_diff": ("strength of schedule", "{:.0%}"),
    "avg_beaten_opp_win_rate_diff": ("quality of wins", "{:.0%}"),
    "avg_lost_to_opp_win_rate_diff": ("quality of losses", "{:.0%}"),
    "avg_win_dominance_diff": ("win dominance", "{:.2f}"),
    "avg_loss_dominance_diff": ("loss competitiveness", "{:.2f}"),
    "finish_speed_diff": ("finish speed", "{:.1f} min"),
    "been_finished_rate_diff": ("finish vulnerability", "{:.0%}"),
    "layoff_diff": ("days since last fight", "{:.0f}"),
    "strike_dropoff_diff": ("late-round cardio", "{:.2f}"),
    "late_round_win_rate_diff": ("late-fight win rate", "{:.0%}"),
    "r1_output_diff": ("R1 striking output", "{:.1f}"),
    "r3_plus_output_diff": ("R3+ striking output", "{:.1f}"),
}


def _get_category(feature_name: str) -> str:
    """Get the category for a feature based on its name."""
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in feature_name:
                return category
    return "other"


def _get_window_label(name: str) -> str:
    if "_last3" in name:
        return "last 3 fights"
    elif "_last5" in name:
        return "last 5 fights"
    return "career"


class Explainer:
    """Generate human-readable explanations for fight predictions using SHAP."""

    def __init__(self, model, feature_names: list[str]):
        self.feature_names = feature_names
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
        if not self.explainer:
            return _fallback_rationale(fighter_1_name, fighter_2_name, f1_win_prob), []

        X = pd.DataFrame([{k: features.get(k, 0) for k in self.feature_names}])
        shap_values = self.explainer.shap_values(X)

        if isinstance(shap_values, list):
            sv = shap_values[1][0]
        else:
            sv = shap_values[0]

        # Build feature importance list
        importances = []
        for i, name in enumerate(self.feature_names):
            importances.append({
                "name": name,
                "shap_value": float(sv[i]),
                "feature_value": float(X.iloc[0, i]),
            })
        importances.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        # Build in-depth rationale
        rationale = _build_detailed_rationale(
            importances, features, fighter_1_name, fighter_2_name, f1_win_prob
        )

        return rationale, importances[:10]


def _build_detailed_rationale(
    importances: list[dict],
    features: dict,
    f1_name: str,
    f2_name: str,
    f1_win_prob: float,
) -> str:
    """Build a detailed, multi-paragraph rationale from SHAP values and features."""
    favored = f1_name if f1_win_prob >= 0.5 else f2_name
    underdog = f2_name if f1_win_prob >= 0.5 else f1_name
    prob = max(f1_win_prob, 1 - f1_win_prob)
    margin = abs(f1_win_prob - 0.5) * 2  # 0 = coin flip, 1 = certain

    # Opening sentence with confidence level
    if margin > 0.4:
        confidence = "strongly"
    elif margin > 0.2:
        confidence = "moderately"
    elif margin > 0.08:
        confidence = "slightly"
    else:
        confidence = "marginally"

    parts = [
        f"The model {confidence} favors {favored} at {prob:.0%} win probability over {underdog}."
    ]

    # Group top features by category
    top_features = importances[:12]
    category_features: dict[str, list[dict]] = {}
    for feat in top_features:
        cat = _get_category(feat["name"])
        category_features.setdefault(cat, []).append(feat)

    # Generate category-specific analysis paragraphs
    category_paragraphs = []

    # Striking analysis
    if "striking" in category_features:
        p = _striking_paragraph(category_features["striking"], features, f1_name, f2_name)
        if p:
            category_paragraphs.append(p)

    # Grappling analysis
    if "grappling" in category_features:
        p = _grappling_paragraph(category_features["grappling"], features, f1_name, f2_name)
        if p:
            category_paragraphs.append(p)

    # Finishing ability
    if "finishing" in category_features:
        p = _finishing_paragraph(category_features["finishing"], features, f1_name, f2_name)
        if p:
            category_paragraphs.append(p)

    # Experience & record
    if "experience" in category_features or "opponent_quality" in category_features:
        combined = category_features.get("experience", []) + category_features.get("opponent_quality", [])
        p = _experience_paragraph(combined, features, f1_name, f2_name)
        if p:
            category_paragraphs.append(p)

    # Physical & conditioning
    if "physical" in category_features or "conditioning" in category_features:
        combined = category_features.get("physical", []) + category_features.get("conditioning", [])
        p = _physical_paragraph(combined, features, f1_name, f2_name)
        if p:
            category_paragraphs.append(p)

    # Dominance
    if "dominance" in category_features:
        p = _dominance_paragraph(category_features["dominance"], features, f1_name, f2_name)
        if p:
            category_paragraphs.append(p)

    parts.extend(category_paragraphs)

    # Build a conclusion that synthesizes the key reasons
    conclusion = _build_conclusion(
        importances[:8], features, f1_name, f2_name, favored, underdog, prob, margin
    )
    if conclusion:
        parts.append(f"Conclusion: {conclusion}")

    return " ".join(parts)


def _build_conclusion(
    top_feats: list[dict],
    features: dict,
    f1: str,
    f2: str,
    favored: str,
    underdog: str,
    prob: float,
    margin: float,
) -> str:
    """Build a short, specific conclusion explaining the model's pick."""
    if margin < 0.08:
        return (
            f"This is essentially a coin-flip. Neither fighter holds a clear statistical edge."
        )

    # Collect specific reasons from the top 3 most impactful features
    reasons_for = []
    reasons_against = []

    for feat in top_feats[:6]:
        name = feat["name"]
        val = feat["feature_value"]
        benefits = f1 if feat["shap_value"] < 0 else f2

        reason = _feature_to_reason(name, val, features, f1, f2, benefits)
        if not reason:
            continue

        if benefits == favored:
            if len(reasons_for) < 2:
                reasons_for.append(reason)
        else:
            if len(reasons_against) < 1:
                reasons_against.append(reason)

    parts = []
    if reasons_for:
        parts.append(f"{favored} wins this because {' and '.join(reasons_for)}.")

    if reasons_against:
        parts.append(f"{underdog}'s best shot is {reasons_against[0]}.")

    return " ".join(parts)


def _feature_to_reason(
    name: str, val: float, features: dict, f1: str, f2: str, benefits: str
) -> str | None:
    """Turn a feature into a short, specific reason."""
    other = f2 if benefits == f1 else f1

    if "knockdown_rate" in name:
        return f"{benefits} has serious knockout power"
    if "sig_strikes_per_min" in name:
        return f"{benefits} is the more active striker"
    if "sig_strike_accuracy" in name:
        return f"{benefits} is the more accurate striker"
    if "sig_strike_defense" in name:
        return f"{benefits} is much harder to hit cleanly"
    if "takedowns_per_15min" in name:
        return f"{benefits} can control where the fight takes place"
    if "takedown_defense" in name:
        return f"{benefits} is very difficult to take down"
    if "control_time_per_15min" in name:
        return f"{benefits} dominates on the ground"
    if "sub_attempts_per_15min" in name:
        return f"{benefits} is a constant submission threat"
    if "finish_rate_ko" in name:
        return f"{benefits} finishes fights by KO at a high rate"
    if "finish_rate_sub" in name:
        return f"{benefits} has a dangerous submission game"
    if "been_finished_rate" in name:
        return f"{other} has been stopped before and is hittable"
    if "win_rate" in name:
        f_wr, o_wr = _get_stat(features, "win_rate")
        if f_wr is not None and o_wr is not None:
            bwr = f_wr if benefits == f1 else o_wr
            return f"{benefits} has a {bwr:.0%} career win rate"
        return f"{benefits} has the better overall record"
    if "win_streak" in name:
        ws = features.get(f"f1_win_streak") if benefits == f1 else features.get(f"f2_win_streak")
        if ws and ws >= 2:
            return f"{benefits} is riding a {int(ws)}-fight win streak with momentum"
        return None
    if "experience" in name:
        return f"{benefits} has significantly more UFC experience"
    if "avg_opp_win_rate" in name:
        return f"{benefits} has been tested against better competition"
    if "avg_win_dominance" in name:
        return f"{benefits} doesn't just win — they dominate"
    if "reach_diff" in name:
        rd = abs(val)
        return f"{benefits} has a {rd:.0f}-inch reach advantage to control distance" if rd >= 2 else None
    if "height_diff" in name:
        return None  # Height alone isn't a compelling reason
    if "age_diff" in name:
        return f"{benefits} has youth on their side"
    if "layoff" in name:
        return f"{other} may be dealing with ring rust from time off"
    if "strike_dropoff" in name or "late_round_win_rate" in name:
        return f"{benefits} has better cardio and finishes fights strong"

    return None


def _get_stat(features: dict, base_key: str, window: str = "career") -> tuple[float | None, float | None]:
    """Get f1 and f2 individual stats from features.

    Tries multiple suffix patterns: _career, _all, _last3, bare key.
    """
    suffixes = [f"_{window}", "_career", "_all", ""]
    for suffix in suffixes:
        f1_val = features.get(f"f1_{base_key}{suffix}")
        f2_val = features.get(f"f2_{base_key}{suffix}")
        if f1_val is not None and f2_val is not None:
            return f1_val, f2_val
    return None, None


def _stat_comparison(f1_val, f2_val, f1_name: str, f2_name: str, label: str, fmt: str) -> str | None:
    """Build a comparison string like 'Fighter A lands 5.2 vs Fighter B's 3.1'."""
    if f1_val is None or f2_val is None:
        return None
    try:
        return f"{f1_name} {fmt.format(f1_val)} vs {f2_name} {fmt.format(f2_val)} {label}"
    except (ValueError, TypeError):
        return None


def _who_has_edge(feat: dict, f1_name: str, f2_name: str) -> tuple[str, str]:
    """Determine which fighter a SHAP value favors. Negative SHAP = favors f1."""
    if feat["shap_value"] < 0:
        return f1_name, f2_name
    return f2_name, f1_name


def _striking_paragraph(feats: list[dict], features: dict, f1: str, f2: str) -> str:
    sentences = ["On the feet:"]

    f1_sig, f2_sig = _get_stat(features, "sig_strikes_per_min")
    if f1_sig is not None and f2_sig is not None:
        sentences.append(
            f"{f1} lands {f1_sig:.1f} significant strikes per minute compared to {f2}'s {f2_sig:.1f}."
        )

    f1_acc, f2_acc = _get_stat(features, "sig_strike_accuracy")
    if f1_acc is not None and f2_acc is not None:
        sentences.append(
            f"{f1} connects at {f1_acc:.0%} accuracy vs {f2}'s {f2_acc:.0%}."
        )

    f1_def, f2_def = _get_stat(features, "sig_strike_defense")
    if f1_def is not None and f2_def is not None:
        better = f1 if f1_def > f2_def else f2
        sentences.append(
            f"{better} is harder to hit with {max(f1_def, f2_def):.0%} strike defense."
        )

    f1_kd, f2_kd = _get_stat(features, "knockdown_rate")
    if f1_kd is not None and f2_kd is not None and (f1_kd > 0.01 or f2_kd > 0.01):
        better = f1 if f1_kd > f2_kd else f2
        sentences.append(
            f"{better} has the higher knockdown rate ({max(f1_kd, f2_kd):.1%} vs {min(f1_kd, f2_kd):.1%})."
        )

    return " ".join(sentences) if len(sentences) > 1 else ""


def _grappling_paragraph(feats: list[dict], features: dict, f1: str, f2: str) -> str:
    sentences = ["In the grappling department:"]

    f1_td, f2_td = _get_stat(features, "takedowns_per_15min")
    if f1_td is not None and f2_td is not None:
        sentences.append(
            f"{f1} averages {f1_td:.1f} takedowns per 15 min vs {f2}'s {f2_td:.1f}."
        )

    f1_tdd, f2_tdd = _get_stat(features, "takedown_defense")
    if f1_tdd is not None and f2_tdd is not None:
        sentences.append(
            f"Takedown defense: {f1} {f1_tdd:.0%} vs {f2} {f2_tdd:.0%}."
        )

    f1_ctrl, f2_ctrl = _get_stat(features, "control_time_per_15min")
    if f1_ctrl is not None and f2_ctrl is not None:
        better = f1 if f1_ctrl > f2_ctrl else f2
        better_val = max(f1_ctrl, f2_ctrl)
        sentences.append(
            f"{better} dominates control time at {better_val:.0f} seconds per 15 minutes."
        )

    f1_sub, f2_sub = _get_stat(features, "sub_attempts_per_15min")
    if f1_sub is not None and f2_sub is not None and (f1_sub > 0.1 or f2_sub > 0.1):
        better = f1 if f1_sub > f2_sub else f2
        sentences.append(
            f"{better} is more active with submissions ({max(f1_sub, f2_sub):.1f} attempts per 15 min)."
        )

    return " ".join(sentences) if len(sentences) > 1 else ""


def _finishing_paragraph(feats: list[dict], features: dict, f1: str, f2: str) -> str:
    sentences = ["Finishing ability:"]

    f1_ko, f2_ko = _get_stat(features, "finish_rate_ko")
    if f1_ko is not None and f2_ko is not None:
        sentences.append(f"KO rate: {f1} {f1_ko:.0%} vs {f2} {f2_ko:.0%}.")

    f1_sub, f2_sub = _get_stat(features, "finish_rate_sub")
    if f1_sub is not None and f2_sub is not None:
        sentences.append(f"Submission rate: {f1} {f1_sub:.0%} vs {f2} {f2_sub:.0%}.")

    f1_vuln, f2_vuln = _get_stat(features, "been_finished_rate")
    if f1_vuln is not None and f2_vuln is not None:
        more_vulnerable = f1 if f1_vuln > f2_vuln else f2
        if max(f1_vuln, f2_vuln) > 0.15:
            sentences.append(
                f"{more_vulnerable} has been finished in {max(f1_vuln, f2_vuln):.0%} of losses, "
                f"a potential vulnerability."
            )

    return " ".join(sentences) if len(sentences) > 1 else ""


def _experience_paragraph(feats: list[dict], features: dict, f1: str, f2: str) -> str:
    sentences = ["Experience and record:"]

    f1_exp = features.get("f1_total_fights_career") or features.get("f1_total_fights_all") or features.get("f1_total_fights")
    f2_exp = features.get("f2_total_fights_career") or features.get("f2_total_fights_all") or features.get("f2_total_fights")
    if f1_exp is not None and f2_exp is not None:
        sentences.append(
            f"{f1} has {int(f1_exp)} UFC fights vs {f2}'s {int(f2_exp)}."
        )

    f1_wr, f2_wr = _get_stat(features, "win_rate")
    if f1_wr is not None and f2_wr is not None:
        sentences.append(f"Win rates: {f1} {f1_wr:.0%} vs {f2} {f2_wr:.0%}.")

    f1_ws = features.get("f1_win_streak")
    f2_ws = features.get("f2_win_streak")
    if f1_ws is not None and f2_ws is not None and (f1_ws >= 2 or f2_ws >= 2):
        if f1_ws >= 2:
            sentences.append(f"{f1} is on a {int(f1_ws)}-fight win streak.")
        if f2_ws >= 2:
            sentences.append(f"{f2} is on a {int(f2_ws)}-fight win streak.")

    f1_opp, f2_opp = _get_stat(features, "avg_opp_win_rate")
    if f1_opp is not None and f2_opp is not None:
        better = f1 if f1_opp > f2_opp else f2
        sentences.append(
            f"{better} has faced tougher opposition "
            f"(opponents' avg win rate: {max(f1_opp, f2_opp):.0%} vs {min(f1_opp, f2_opp):.0%})."
        )

    return " ".join(sentences) if len(sentences) > 1 else ""


def _physical_paragraph(feats: list[dict], features: dict, f1: str, f2: str) -> str:
    sentences = []

    height_diff = features.get("height_diff")
    reach_diff = features.get("reach_diff")
    if height_diff is not None and reach_diff is not None:
        if abs(height_diff) >= 1 or abs(reach_diff) >= 1:
            taller = f1 if height_diff > 0 else f2
            longer = f1 if reach_diff > 0 else f2
            parts = []
            if abs(height_diff) >= 1:
                parts.append(f"{taller} has a {abs(height_diff):.0f}-inch height advantage")
            if abs(reach_diff) >= 1:
                parts.append(f"{longer} has a {abs(reach_diff):.0f}-inch reach advantage")
            sentences.append(" and ".join(parts) + ".")

    f1_layoff = features.get("f1_layoff_days")
    f2_layoff = features.get("f2_layoff_days")
    if f1_layoff is not None and f2_layoff is not None:
        if max(f1_layoff, f2_layoff) > 300:
            rusty = f1 if f1_layoff > f2_layoff else f2
            days = int(max(f1_layoff, f2_layoff))
            sentences.append(
                f"{rusty} hasn't fought in {days} days, which could mean ring rust."
            )

    f1_cardio, f2_cardio = _get_stat(features, "strike_dropoff")
    if f1_cardio is not None and f2_cardio is not None:
        if abs(f1_cardio - f2_cardio) > 0.05:
            better = f1 if f1_cardio > f2_cardio else f2
            sentences.append(
                f"{better} maintains better striking output in later rounds, suggesting superior cardio."
            )

    return ("Physical and conditioning: " + " ".join(sentences)) if sentences else ""


def _dominance_paragraph(feats: list[dict], features: dict, f1: str, f2: str) -> str:
    sentences = []

    f1_wd, f2_wd = _get_stat(features, "avg_win_dominance")
    if f1_wd is not None and f2_wd is not None:
        if abs(f1_wd - f2_wd) > 0.05:
            more_dominant = f1 if f1_wd > f2_wd else f2
            sentences.append(
                f"{more_dominant} wins more decisively (dominance score {max(f1_wd, f2_wd):.2f} vs {min(f1_wd, f2_wd):.2f})."
            )

    f1_ld, f2_ld = _get_stat(features, "avg_loss_dominance")
    if f1_ld is not None and f2_ld is not None:
        if abs(f1_ld - f2_ld) > 0.05:
            more_competitive = f1 if f1_ld < f2_ld else f2
            sentences.append(
                f"In losses, {more_competitive} tends to keep fights closer, showing resilience."
            )

    return ("Fight dominance: " + " ".join(sentences)) if sentences else ""


def _fallback_rationale(f1_name: str, f2_name: str, f1_win_prob: float) -> str:
    """Generate a basic rationale when SHAP is not available."""
    favored = f1_name if f1_win_prob >= 0.5 else f2_name
    prob = max(f1_win_prob, 1 - f1_win_prob)
    return f"{favored} is favored at {prob:.0%} based on historical fight statistics and matchup analysis."
