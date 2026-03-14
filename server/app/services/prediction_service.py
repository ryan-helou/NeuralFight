"""Orchestrates the full prediction pipeline: features -> predict -> explain -> store."""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.explainer import Explainer
from app.ml.features import FeatureBuilder
from app.ml.predictor import Predictor
from app.ml.upset_detector import (
    compute_betting_confidence,
    compute_upset_score,
    decimal_to_implied_prob,
)
from app.models import BettingOdds, Fight, Fighter, Prediction

logger = logging.getLogger(__name__)

MODEL_VERSION = "v1"


class PredictionService:
    def __init__(self, session: Session):
        self.session = session
        self._predictor = None
        self._explainer = None

    def _ensure_models_loaded(self):
        if self._predictor is None:
            self._predictor = Predictor()
            self._predictor.load_models()

            # Initialize explainer with the winner model
            import joblib
            winner_data = joblib.load(Path(__file__).parent.parent / "ml" / "models" / "winner_v1.joblib")
            self._explainer = Explainer(winner_data["model"], winner_data["features"])

    def get_or_create_prediction(self, fight_id: int) -> Prediction | None:
        """Get cached prediction or generate a new one."""
        existing = self.session.execute(
            select(Prediction).where(
                Prediction.fight_id == fight_id,
                Prediction.model_version == MODEL_VERSION,
            ).order_by(Prediction.created_at.desc()).limit(1)
        ).scalar_one_or_none()

        if existing:
            return existing

        return self.generate_prediction(fight_id)

    def generate_prediction(self, fight_id: int) -> Prediction | None:
        """Generate a fresh prediction for a fight. Skips if one already exists."""
        # Prevent duplicates — check if prediction already exists
        existing = self.session.execute(
            select(Prediction).where(
                Prediction.fight_id == fight_id,
                Prediction.model_version == MODEL_VERSION,
            ).limit(1)
        ).scalar_one_or_none()
        if existing:
            return existing

        self._ensure_models_loaded()

        # Build features
        feature_builder = FeatureBuilder(self.session)
        features = feature_builder.build_fight_features(fight_id)
        if features is None:
            logger.warning(f"Could not build features for fight {fight_id}")
            return None

        # Get fight details for names
        fight = self.session.get(Fight, fight_id)
        if not fight:
            return None

        f1 = self.session.get(Fighter, fight.fighter_1_id)
        f2 = self.session.get(Fighter, fight.fighter_2_id)

        # Run prediction
        prediction = self._predictor.predict(features)

        # Generate explanation
        rationale, feature_importances = self._explainer.explain(
            features, f1.name, f2.name, prediction.fighter_1_win_prob
        )

        # Get betting odds for upset detection
        upset_score = None
        betting_confidence = None
        odds = self.session.execute(
            select(BettingOdds)
            .where(BettingOdds.fight_id == fight_id)
            .order_by(BettingOdds.retrieved_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if odds:
            implied_f1 = decimal_to_implied_prob(odds.fighter_1_decimal)
            implied_f2 = decimal_to_implied_prob(odds.fighter_2_decimal)

            # Determine who the betting underdog is
            if implied_f1 < implied_f2:
                # f1 is the underdog
                upset_score = compute_upset_score(prediction.fighter_1_win_prob, implied_f1)
            else:
                upset_score = compute_upset_score(prediction.fighter_2_win_prob, implied_f2)

            # Betting confidence for the ML favorite
            if prediction.fighter_1_win_prob >= 0.5:
                betting_confidence = compute_betting_confidence(prediction.fighter_1_win_prob, implied_f1)
            else:
                betting_confidence = compute_betting_confidence(prediction.fighter_2_win_prob, implied_f2)

        # Store prediction
        db_prediction = Prediction(
            fight_id=fight_id,
            model_version=MODEL_VERSION,
            fighter_1_win_prob=prediction.fighter_1_win_prob,
            fighter_2_win_prob=prediction.fighter_2_win_prob,
            ko_tko_prob=prediction.method_probs.get("ko_tko"),
            submission_prob=prediction.method_probs.get("submission"),
            decision_prob=prediction.method_probs.get("decision"),
            predicted_round=None,
            round_probabilities=None,
            method_by_fighter=prediction.method_by_fighter,
            upset_score=upset_score,
            betting_confidence=betting_confidence,
            rationale=rationale,
            feature_importances=[
                {"name": fi["name"], "shap_value": fi.get("shap_value", 0)}
                for fi in feature_importances[:10]
            ] if feature_importances else prediction.top_features,
        )
        self.session.add(db_prediction)
        self.session.commit()

        return db_prediction
