"""Model performance evaluation endpoint.

Runs the trained model on the held-out test set (last 15% of fights
chronologically) and returns accuracy stats compared to baseline.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Event, Fight, Fighter
from app.models.betting_odds import BettingOdds

router = APIRouter(prefix="/api/performance", tags=["performance"])

CACHE_DIR = Path(__file__).parent.parent.parent / "scripts" / ".cache"
MODEL_DIR = Path(__file__).parent.parent / "ml" / "models"

# Cache the results so we don't recompute every request
_cached_results = None


def _evaluate() -> dict:
    """Run model evaluation on the test set."""
    global _cached_results
    if _cached_results is not None:
        return _cached_results

    features_path = CACHE_DIR / "features.parquet"
    targets_path = CACHE_DIR / "targets.parquet"

    if not features_path.exists() or not targets_path.exists():
        return {"error": "Feature cache not found. Train the model first."}

    features_df = pd.read_parquet(features_path)
    targets_df = pd.read_parquet(targets_path)

    X = features_df.drop(columns=["fight_id"], errors="ignore")
    fight_ids = features_df["fight_id"].values if "fight_id" in features_df.columns else None

    # Same split as training: 70/15/15
    n = len(X)
    val_end = int(n * 0.85)
    X_test = X.iloc[val_end:]
    y_test = targets_df["winner"].iloc[val_end:]
    test_fight_ids = fight_ids[val_end:] if fight_ids is not None else None
    test_methods = targets_df["method_category"].iloc[val_end:].values

    # Load winner model
    winner_data = joblib.load(MODEL_DIR / "winner_v1.joblib")
    model = winner_data["model"]

    # Predict
    probs = model.predict_proba(X_test)
    if probs.shape[1] == 1:
        if hasattr(model, "classes_") and model.classes_[0] == 1:
            f2_probs = probs[:, 0]
        else:
            f2_probs = 1 - probs[:, 0]
    else:
        f2_probs = probs[:, 1]

    preds = (f2_probs >= 0.5).astype(int)
    correct = (preds == y_test.values).astype(int)

    # Overall accuracy
    accuracy = float(correct.mean())

    # Confidence buckets
    confidence = np.maximum(f2_probs, 1 - f2_probs)
    buckets = [
        ("50-55%", 0.50, 0.55),
        ("55-60%", 0.55, 0.60),
        ("60-65%", 0.60, 0.65),
        ("65-70%", 0.65, 0.70),
        ("70-75%", 0.70, 0.75),
        ("75%+", 0.75, 1.01),
    ]
    bucket_stats = []
    for label, lo, hi in buckets:
        mask = (confidence >= lo) & (confidence < hi)
        if mask.sum() > 0:
            bucket_stats.append({
                "bucket": label,
                "count": int(mask.sum()),
                "accuracy": float(correct[mask].mean()),
                "avg_confidence": float(confidence[mask].mean()),
            })

    # Accuracy by method
    method_stats = []
    for method in ["ko_tko", "submission", "decision"]:
        mask = test_methods == method
        if mask.sum() > 0:
            method_stats.append({
                "method": method.replace("_", "/").upper() if method == "ko_tko" else method.capitalize(),
                "count": int(mask.sum()),
                "accuracy": float(correct[mask].mean()),
            })

    # Fight-by-fight results with Vegas comparison + betting simulation
    fight_results = []
    vegas_correct_count = 0
    vegas_total_count = 0

    # Value-based betting simulation
    STARTING_BANKROLL = 10_000.0
    BASE_UNIT = 100.0  # 1% of starting bankroll
    MAX_BET = 500.0    # 5% cap
    MIN_EDGE = 0.03    # Only bet when edge > 3%
    bankroll = STARTING_BANKROLL
    total_wagered = 0.0
    total_profit = 0.0
    bets_won = 0
    bets_lost = 0
    bet_history = []  # chronological for P&L curve

    if test_fight_ids is not None:
        engine = create_engine(settings.database_url_sync)
        with Session(engine) as session:
            for idx in range(len(test_fight_ids)):
                fid = int(test_fight_ids[idx])
                fight = session.get(Fight, fid)
                if not fight:
                    continue

                f1 = session.get(Fighter, fight.fighter_1_id)
                f2 = session.get(Fighter, fight.fighter_2_id)
                event = session.get(Event, fight.event_id)

                f1_prob = float(1 - f2_probs[idx])
                f2_prob = float(f2_probs[idx])
                predicted_winner = f2.name if f2_prob >= 0.5 else f1.name
                actual_winner = fight.winner.name if fight.winner else None
                was_correct = bool(correct[idx])

                # Look up betting odds
                odds = session.execute(
                    select(BettingOdds)
                    .where(BettingOdds.fight_id == fid)
                    .order_by(BettingOdds.retrieved_at.desc())
                    .limit(1)
                ).scalar_one_or_none()

                vegas_pick = None
                vegas_was_correct = None
                bet_info = None

                if odds and f1 and f2:
                    implied_f1 = 1.0 / odds.fighter_1_decimal if odds.fighter_1_decimal > 0 else 0
                    implied_f2 = 1.0 / odds.fighter_2_decimal if odds.fighter_2_decimal > 0 else 0

                    if actual_winner:
                        vegas_pick = f1.name if implied_f1 >= implied_f2 else f2.name
                        vegas_was_correct = vegas_pick == actual_winner
                        vegas_total_count += 1
                        if vegas_was_correct:
                            vegas_correct_count += 1

                    # Value-based bet: find the fighter with the biggest edge
                    edge_f1 = f1_prob - implied_f1
                    edge_f2 = f2_prob - implied_f2
                    best_edge = max(edge_f1, edge_f2)

                    if best_edge >= MIN_EDGE and actual_winner:
                        # Bet on the value side
                        if edge_f1 > edge_f2:
                            bet_on = f1.name
                            bet_decimal = odds.fighter_1_decimal
                            bet_edge = edge_f1
                        else:
                            bet_on = f2.name
                            bet_decimal = odds.fighter_2_decimal
                            bet_edge = edge_f2

                        # Size: scale by edge, bigger edge = bigger bet
                        bet_amount = min(BASE_UNIT * (bet_edge / 0.05), MAX_BET)
                        bet_amount = min(bet_amount, bankroll)  # can't bet more than we have

                        if bet_amount > 0:
                            won = bet_on == actual_winner
                            payout = bet_amount * (bet_decimal - 1) if won else -bet_amount
                            bankroll += payout
                            total_wagered += bet_amount
                            total_profit += payout

                            if won:
                                bets_won += 1
                            else:
                                bets_lost += 1

                            bet_info = {
                                "bet_on": bet_on,
                                "bet_amount": round(bet_amount, 2),
                                "decimal_odds": round(bet_decimal, 2),
                                "edge": round(bet_edge, 3),
                                "won": won,
                                "payout": round(payout, 2),
                            }

                            bet_history.append({
                                "fight_id": fid,
                                "bankroll": round(bankroll, 2),
                                "profit": round(payout, 2),
                            })

                fight_results.append({
                    "fight_id": fid,
                    "fighter_1_name": f1.name if f1 else "?",
                    "fighter_2_name": f2.name if f2 else "?",
                    "event_name": event.name if event else "?",
                    "fighter_1_prob": round(f1_prob, 3),
                    "fighter_2_prob": round(f2_prob, 3),
                    "predicted_winner": predicted_winner,
                    "actual_winner": actual_winner,
                    "correct": was_correct,
                    "confidence": round(float(confidence[idx]), 3),
                    "method": fight.method or "",
                    "vegas_pick": vegas_pick,
                    "vegas_correct": vegas_was_correct,
                    "bet": bet_info,
                })

            fight_results.reverse()

    vegas_accuracy = round(vegas_correct_count / vegas_total_count, 4) if vegas_total_count > 0 else None
    roi = round((total_profit / total_wagered) * 100, 2) if total_wagered > 0 else None

    _cached_results = {
        "test_size": int(len(X_test)),
        "accuracy": round(accuracy, 4),
        "vegas_baseline": vegas_accuracy,
        "vegas_sample_size": vegas_total_count,
        "bucket_stats": bucket_stats,
        "method_stats": method_stats,
        "recent_fights": fight_results[:50],
        "betting": {
            "starting_bankroll": STARTING_BANKROLL,
            "final_bankroll": round(bankroll, 2),
            "total_profit": round(total_profit, 2),
            "total_wagered": round(total_wagered, 2),
            "roi": roi,
            "bets_placed": bets_won + bets_lost,
            "bets_won": bets_won,
            "bets_lost": bets_lost,
            "win_rate": round(bets_won / (bets_won + bets_lost) * 100, 1) if (bets_won + bets_lost) > 0 else None,
            "history": bet_history,
        },
    }
    return _cached_results


@router.get("")
def get_performance():
    """Get model performance stats on the held-out test set."""
    return _evaluate()
