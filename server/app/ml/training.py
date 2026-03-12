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
from sklearn.model_selection import PredefinedSplit
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
        return log_loss(y_val, preds, labels=[0, 1])

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)

    best_params = study.best_params
    best_params["verbose"] = -1
    logger.info(f"Best binary params: {best_params}")

    # Calibrate using PredefinedSplit so only the val fold is used for calibration
    X_combined = pd.concat([X_train, X_val], ignore_index=True)
    y_combined = pd.concat([y_train, y_val], ignore_index=True)
    # -1 = training fold (not used for calibration), 0 = validation fold
    test_fold = np.array([-1] * len(X_train) + [0] * len(X_val))
    ps = PredefinedSplit(test_fold)

    calibrated = CalibratedClassifierCV(
        lgb.LGBMClassifier(**best_params), cv=ps, method="sigmoid"
    )
    calibrated.fit(X_combined, y_combined)

    return calibrated


def _pad_proba(probs: np.ndarray, model_classes: np.ndarray, num_class: int) -> np.ndarray:
    """Pad predict_proba output to have columns for all expected classes.

    LightGBM may return fewer columns if some classes weren't seen in training.
    """
    if probs.shape[1] == num_class:
        return probs
    padded = np.zeros((probs.shape[0], num_class))
    for i, cls in enumerate(model_classes):
        if cls < num_class:
            padded[:, cls] = probs[:, i]
    return padded


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
        preds = _pad_proba(model.predict_proba(X_val), model.classes_, num_class)
        return log_loss(y_val, preds, labels=list(range(num_class)))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)

    best_params = study.best_params
    best_params["num_class"] = num_class
    best_params["verbose"] = -1
    logger.info(f"Best multiclass params: {best_params}")

    # Calibrate using PredefinedSplit so only the val fold is used for calibration
    X_combined = pd.concat(
        [pd.DataFrame(X_train), pd.DataFrame(X_val)], ignore_index=True
    )
    y_combined = np.concatenate([y_train, y_val])
    test_fold = np.array([-1] * len(X_train) + [0] * len(X_val))
    ps = PredefinedSplit(test_fold)

    calibrated = CalibratedClassifierCV(
        lgb.LGBMClassifier(**best_params), cv=ps, method="sigmoid"
    )
    calibrated.fit(X_combined, y_combined)

    return calibrated


def _get_binary_probs(model, X: pd.DataFrame) -> np.ndarray:
    """Get probability of class 1 from a model, handling single-column edge case."""
    proba = model.predict_proba(X)
    if proba.shape[1] == 1:
        # Model only outputs one column — check which class it represents
        if hasattr(model, "classes_") and model.classes_[0] == 1:
            return proba[:, 0]
        return 1 - proba[:, 0]
    return proba[:, 1]


def _evaluate_binary(model, X_test: pd.DataFrame, y_test: pd.Series, name: str):
    """Log evaluation metrics for a binary model."""
    probs = _get_binary_probs(model, X_test)
    preds = (probs >= 0.5).astype(int)
    acc = accuracy_score(y_test, preds)
    ll = log_loss(y_test, probs, labels=[0, 1])
    brier = brier_score_loss(y_test, probs)
    logger.info(f"{name} Model — Accuracy: {acc:.3f} | Log Loss: {ll:.3f} | Brier: {brier:.3f}")


def _evaluate_multiclass(
    model, X_test: pd.DataFrame, y_test: np.ndarray, name: str, labels: list[str]
):
    """Log evaluation metrics for a multiclass model."""
    probs = model.predict_proba(X_test)
    num_class = len(labels)
    if probs.shape[1] != num_class:
        probs = _pad_proba(probs, model.classes_, num_class)
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    ll = log_loss(y_test, probs, labels=list(range(num_class)))
    logger.info(f"{name} Model — Accuracy: {acc:.3f} | Log Loss: {ll:.3f}")
