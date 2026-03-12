"""Inference engine that combines all three models into unified fight predictions."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"


@dataclass
class FightPrediction:
    fight_id: int
    fighter_1_win_prob: float
    fighter_2_win_prob: float
    method_probs: dict[str, float]  # {"ko_tko": 0.35, "submission": 0.20, "decision": 0.45}
    method_by_fighter: dict  # {f1: {ko: ..., sub: ..., dec: ...}, f2: {...}}
    round_probs: dict[str, float]  # {"1": 0.10, ..., "decision": 0.45}
    round_by_fighter: dict  # {f1: {1: ..., ...}, f2: {1: ..., ...}}
    top_features: list[dict] = field(default_factory=list)


class Predictor:
    """Loads trained models and produces unified fight predictions."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = model_dir
        self._winner_model = None
        self._method_model = None
        self._round_model = None
        self._feature_names = None
        self._method_encoder = None
        self._round_encoder = None

    def load_models(self):
        """Load all serialized models from disk."""
        winner_data = joblib.load(self.model_dir / "winner_v1.joblib")
        self._winner_model = winner_data["model"]
        self._feature_names = winner_data["features"]

        method_data = joblib.load(self.model_dir / "method_v1.joblib")
        self._method_model = method_data["model"]
        self._method_encoder = method_data["encoder"]

        round_data = joblib.load(self.model_dir / "round_v1.joblib")
        self._round_model = round_data["model"]
        self._round_encoder = round_data["encoder"]

        logger.info("All models loaded successfully")

    def predict(self, features: dict) -> FightPrediction:
        """Generate a full prediction from a feature dictionary.

        Args:
            features: Dict of feature values (from FeatureBuilder).

        Returns:
            FightPrediction with all probability breakdowns.
        """
        fight_id = features.get("fight_id", 0)

        # Prepare feature vector
        X = pd.DataFrame([{k: features.get(k, 0) for k in self._feature_names}])

        # Winner probabilities
        winner_probs = self._winner_model.predict_proba(X)[0]
        if len(winner_probs) == 1:
            # Single-column edge case from CalibratedClassifierCV
            classes = self._winner_model.classes_
            if classes[0] == 1:
                f1_win = float(winner_probs[0])
            else:
                f1_win = 1.0 - float(winner_probs[0])
            f2_win = 1.0 - f1_win
        else:
            f1_win = float(winner_probs[0])  # P(fighter_1 wins)
            f2_win = float(winner_probs[1])  # P(fighter_2 wins)

        # Method probabilities (overall)
        method_probs_raw = self._method_model.predict_proba(X)[0]
        method_labels = self._method_encoder.classes_
        method_probs = {label: float(prob) for label, prob in zip(method_labels, method_probs_raw)}

        # Method by fighter: P(f1 wins by KO) = P(f1 wins) * P(KO | f1 wins)
        # We approximate P(method | fighter wins) by scaling method probs by winner probs
        method_by_fighter = {
            "fighter_1": {m: round(f1_win * p, 4) for m, p in method_probs.items()},
            "fighter_2": {m: round(f2_win * p, 4) for m, p in method_probs.items()},
        }

        # Round probabilities (overall)
        round_probs_raw = self._round_model.predict_proba(X)[0]
        round_labels = self._round_encoder.classes_
        round_probs = {}
        for label, prob in zip(round_labels, round_probs_raw):
            key = "decision" if label == 0 else str(label)
            round_probs[key] = float(prob)

        # Round by fighter
        round_by_fighter = {
            "fighter_1": {k: round(f1_win * v, 4) for k, v in round_probs.items()},
            "fighter_2": {k: round(f2_win * v, 4) for k, v in round_probs.items()},
        }

        # Get feature importances from the base estimator
        top_features = self._get_top_features(X)

        return FightPrediction(
            fight_id=fight_id,
            fighter_1_win_prob=round(f1_win, 4),
            fighter_2_win_prob=round(f2_win, 4),
            method_probs={k: round(v, 4) for k, v in method_probs.items()},
            method_by_fighter=method_by_fighter,
            round_probs={k: round(v, 4) for k, v in round_probs.items()},
            round_by_fighter=round_by_fighter,
            top_features=top_features,
        )

    def _get_top_features(self, X: pd.DataFrame, n: int = 10) -> list[dict]:
        """Get the top N most important features for a prediction.

        Uses the base LightGBM model's feature importances weighted by feature values.
        """
        try:
            # Access the base estimator inside CalibratedClassifierCV
            base_model = self._winner_model.calibrated_classifiers_[0].estimator
            importances = base_model.feature_importances_
            feature_names = self._feature_names

            # Sort by importance
            indices = np.argsort(importances)[::-1][:n]
            top = []
            for idx in indices:
                top.append({
                    "name": feature_names[idx],
                    "importance": float(importances[idx]),
                    "value": float(X.iloc[0, idx]),
                })
            return top
        except Exception:
            return []
