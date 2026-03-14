"""Inference engine that combines winner and method models into unified fight predictions."""

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
    top_features: list[dict] = field(default_factory=list)


class Predictor:
    """Loads trained models and produces unified fight predictions."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = model_dir
        self._winner_model = None
        self._method_model = None
        self._feature_names = None
        self._method_encoder = None

    def load_models(self):
        """Load all serialized models from disk."""
        winner_data = joblib.load(self.model_dir / "winner_v1.joblib")
        self._winner_model = winner_data["model"]
        self._feature_names = winner_data["features"]

        method_data = joblib.load(self.model_dir / "method_v1.joblib")
        self._method_model = method_data["model"]
        self._method_encoder = method_data["encoder"]

        logger.info("All models loaded successfully")

    def predict(self, features: dict) -> FightPrediction:
        """Generate a full prediction from a feature dictionary.

        Returns:
            FightPrediction with winner and method probability breakdowns.
        """
        fight_id = features.get("fight_id", 0)

        # Prepare feature vector
        X = pd.DataFrame([{k: features.get(k, 0) for k in self._feature_names}])

        # Winner probabilities
        winner_probs = self._winner_model.predict_proba(X)[0]
        if len(winner_probs) == 1:
            classes = self._winner_model.classes_
            if classes[0] == 1:
                f1_win = float(winner_probs[0])
            else:
                f1_win = 1.0 - float(winner_probs[0])
            f2_win = 1.0 - f1_win
        else:
            f1_win = float(winner_probs[0])
            f2_win = float(winner_probs[1])

        # Method probabilities (overall)
        method_probs_raw = self._method_model.predict_proba(X)[0]
        method_labels = self._method_encoder.classes_
        method_probs = {label: float(prob) for label, prob in zip(method_labels, method_probs_raw)}

        # Method by fighter: P(f1 wins by KO) = P(f1 wins) * P(KO)
        method_by_fighter = {
            "fighter_1": {m: round(f1_win * p, 4) for m, p in method_probs.items()},
            "fighter_2": {m: round(f2_win * p, 4) for m, p in method_probs.items()},
        }

        # Get feature importances
        top_features = self._get_top_features(X)

        return FightPrediction(
            fight_id=fight_id,
            fighter_1_win_prob=round(f1_win, 4),
            fighter_2_win_prob=round(f2_win, 4),
            method_probs={k: round(v, 4) for k, v in method_probs.items()},
            method_by_fighter=method_by_fighter,
            top_features=top_features,
        )

    def _get_top_features(self, X: pd.DataFrame, n: int = 10) -> list[dict]:
        """Get the top N most important features for a prediction."""
        try:
            base_model = self._winner_model.calibrated_classifiers_[0].estimator
            importances = base_model.feature_importances_
            feature_names = self._feature_names

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
