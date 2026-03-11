"""Model training pipeline for NeuralFight.

Trains three LightGBM models:
1. Winner prediction (binary)
2. Method of victory (multiclass: ko_tko, submission, decision)
3. Round of finish (multiclass: 1-5, decision)

Uses time-series split and Optuna hyperparameter tuning.
"""

import logging
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

# Method and round label mappings
METHOD_LABELS = ["ko_tko", "submission", "decision"]
ROUND_LABELS = [0, 1, 2, 3, 4, 5]  # 0 = goes to decision


def train_all(features_df: pd.DataFrame, targets_df: pd.DataFrame, n_trials: int = 50):
    """Train all three models and save them.

    Args:
        features_df: Feature matrix (one row per fight).
        targets_df: Target variables with columns: fight_id, winner, method_category, finish_round, is_decision.
        n_trials: Number of Optuna trials for hyperparameter search.
    """
    # Drop fight_id from features
    X = features_df.drop(columns=["fight_id"], errors="ignore")
    feature_names = list(X.columns)

    # Time-series split: we rely on the data being ordered chronologically
    n = len(X)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)

    X_train, X_val, X_test = X.iloc[:train_end], X.iloc[train_end:val_end], X.iloc[val_end:]

    logger.info(f"Dataset: {n} fights | Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # 1. Winner model
    logger.info("Training winner model...")
    y_winner = targets_df["winner"]
    winner_model = _train_binary_model(
        X_train, y_winner.iloc[:train_end],
        X_val, y_winner.iloc[train_end:val_end],
        n_trials=n_trials,
    )
    _evaluate_binary(winner_model, X_test, y_winner.iloc[val_end:], "Winner")
    joblib.dump({"model": winner_model, "features": feature_names}, MODEL_DIR / "winner_v1.joblib")

    # 2. Method model
    logger.info("Training method model...")
    method_encoder = LabelEncoder()
    method_encoder.fit(METHOD_LABELS)
    y_method = method_encoder.transform(
        targets_df["method_category"].apply(lambda x: x if x in METHOD_LABELS else "decision")
    )
    method_model = _train_multiclass_model(
        X_train, y_method[:train_end],
        X_val, y_method[train_end:val_end],
        num_class=len(METHOD_LABELS),
        n_trials=n_trials,
    )
    _evaluate_multiclass(method_model, X_test, y_method[val_end:], "Method", METHOD_LABELS)
    joblib.dump(
        {"model": method_model, "encoder": method_encoder, "features": feature_names},
        MODEL_DIR / "method_v1.joblib",
    )

    # 3. Round model
    logger.info("Training round model...")
    round_encoder = LabelEncoder()
    round_encoder.fit(ROUND_LABELS)
    y_round = round_encoder.transform(
        targets_df["finish_round"].apply(lambda x: x if x in ROUND_LABELS else 0)
    )
    round_model = _train_multiclass_model(
        X_train, y_round[:train_end],
        X_val, y_round[train_end:val_end],
        num_class=len(ROUND_LABELS),
        n_trials=n_trials,
    )
    _evaluate_multiclass(round_model, X_test, y_round[val_end:], "Round", [str(r) for r in ROUND_LABELS])
    joblib.dump(
        {"model": round_model, "encoder": round_encoder, "features": feature_names},
        MODEL_DIR / "round_v1.joblib",
    )

    logger.info(f"All models saved to {MODEL_DIR}")


def _train_binary_model(
    X_train: pd.DataFrame, y_train: pd.Series,
    X_val: pd.DataFrame, y_val: pd.Series,
    n_trials: int = 50,
) -> CalibratedClassifierCV:
    """Train a binary LightGBM classifier with Optuna tuning and calibration."""

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "verbose": -1,
        }
        model = lgb.LGBMClassifier(**params)
        model.fit(X_train, y_train)
        preds = model.predict_proba(X_val)[:, 1]
        return log_loss(y_val, preds)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)

    best_params = study.best_params
    best_params["verbose"] = -1
    logger.info(f"Best binary params: {best_params}")

    model = lgb.LGBMClassifier(**best_params)
    model.fit(X_train, y_train)

    # Calibrate probabilities
    calibrated = CalibratedClassifierCV(model, cv="prefit", method="isotonic")
    calibrated.fit(X_val, y_val)

    return calibrated


def _train_multiclass_model(
    X_train: pd.DataFrame, y_train: np.ndarray,
    X_val: pd.DataFrame, y_val: np.ndarray,
    num_class: int,
    n_trials: int = 50,
) -> CalibratedClassifierCV:
    """Train a multiclass LightGBM classifier with Optuna tuning and calibration."""

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 800),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "num_class": num_class,
            "verbose": -1,
        }
        model = lgb.LGBMClassifier(**params)
        model.fit(X_train, y_train)
        preds = model.predict_proba(X_val)
        return log_loss(y_val, preds)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)

    best_params = study.best_params
    best_params["num_class"] = num_class
    best_params["verbose"] = -1
    logger.info(f"Best multiclass params: {best_params}")

    model = lgb.LGBMClassifier(**best_params)
    model.fit(X_train, y_train)

    calibrated = CalibratedClassifierCV(model, cv="prefit", method="isotonic")
    calibrated.fit(X_val, y_val)

    return calibrated


def _evaluate_binary(model, X_test: pd.DataFrame, y_test: pd.Series, name: str):
    """Log evaluation metrics for a binary model."""
    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)
    acc = accuracy_score(y_test, preds)
    ll = log_loss(y_test, probs)
    brier = brier_score_loss(y_test, probs)
    logger.info(f"{name} Model — Accuracy: {acc:.3f} | Log Loss: {ll:.3f} | Brier: {brier:.3f}")


def _evaluate_multiclass(
    model, X_test: pd.DataFrame, y_test: np.ndarray, name: str, labels: list[str]
):
    """Log evaluation metrics for a multiclass model."""
    probs = model.predict_proba(X_test)
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    ll = log_loss(y_test, probs)
    logger.info(f"{name} Model — Accuracy: {acc:.3f} | Log Loss: {ll:.3f}")
