from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database import get_session, get_sync_session
from app.models import Event, Fight, Fighter, Prediction
from app.models.betting_odds import BettingOdds
from app.schemas.prediction import BetHistoryOut, PredictionOut, UpsetOut, ValueBetOut
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.post("/fight/{fight_id}", response_model=PredictionOut)
def generate_prediction(fight_id: int, session: Session = Depends(get_sync_session)):
    """Generate a prediction for a fight (sync, since ML inference is CPU-bound)."""
    service = PredictionService(session)
    prediction = service.get_or_create_prediction(fight_id)
    if not prediction:
        raise HTTPException(400, "Could not generate prediction. Fighter history may be insufficient.")
    return prediction


@router.get("/fight/{fight_id}", response_model=PredictionOut)
async def get_prediction(fight_id: int, session: AsyncSession = Depends(get_session)):
    pred = (
        await session.execute(
            select(Prediction)
            .where(Prediction.fight_id == fight_id)
            .order_by(Prediction.created_at.desc())
        )
    ).scalars().first()

    if not pred:
        raise HTTPException(404, "No prediction found. Generate one first via POST.")
    return pred


@router.post("/event/{event_id}")
def generate_event_predictions(event_id: int, session: Session = Depends(get_sync_session)):
    """Generate predictions for all fights in an event."""
    fights = session.execute(
        select(Fight).where(Fight.event_id == event_id)
    ).scalars().all()

    service = PredictionService(session)
    generated = 0
    for fight in fights:
        try:
            pred = service.get_or_create_prediction(fight.id)
            if pred:
                generated += 1
        except Exception:
            continue

    return {"generated": generated, "total": len(fights)}


@router.post("/generate-upcoming")
def generate_upcoming_predictions(session: Session = Depends(get_sync_session)):
    """Generate predictions for all upcoming fights that don't have one yet."""
    upcoming_fights = session.execute(
        select(Fight)
        .join(Event, Fight.event_id == Event.id)
        .where(Event.date >= date.today())
        .where(Fight.result.is_(None))
    ).scalars().all()

    # Filter to fights without predictions
    fights_needing_preds = []
    for fight in upcoming_fights:
        existing = session.execute(
            select(Prediction).where(Prediction.fight_id == fight.id).limit(1)
        ).scalar_one_or_none()
        if not existing:
            fights_needing_preds.append(fight)

    if not fights_needing_preds:
        return {"generated": 0, "total": len(upcoming_fights), "already_done": True}

    service = PredictionService(session)
    generated = 0
    for fight in fights_needing_preds:
        try:
            pred = service.generate_prediction(fight.id)
            if pred:
                generated += 1
        except Exception:
            continue

    return {"generated": generated, "total": len(upcoming_fights)}


@router.get("/upcoming", response_model=list[PredictionOut])
async def get_upcoming_predictions(session: AsyncSession = Depends(get_session)):
    """Get predictions for the next upcoming event."""
    # Find the next event
    next_event = (
        await session.execute(
            select(Event).where(Event.date >= date.today()).order_by(Event.date).limit(1)
        )
    ).scalars().first()

    if not next_event:
        return []

    # Get all fights for that event
    fights = (
        await session.execute(
            select(Fight).where(Fight.event_id == next_event.id)
        )
    ).scalars().all()

    # Get predictions
    predictions = []
    for fight in fights:
        pred = (
            await session.execute(
                select(Prediction)
                .where(Prediction.fight_id == fight.id)
                .order_by(Prediction.created_at.desc())
            )
        ).scalars().first()
        if pred:
            predictions.append(pred)

    return predictions


@router.get("/upsets", response_model=list[UpsetOut])
async def get_upsets(
    min_score: float = 30.0,
    session: AsyncSession = Depends(get_session),
):
    """Get fights where ML disagrees with betting odds."""
    # Subquery: latest prediction id per fight
    latest_ids = (
        select(func.max(Prediction.id).label("id"))
        .group_by(Prediction.fight_id)
        .subquery()
    )
    preds = (
        await session.execute(
            select(Prediction)
            .join(latest_ids, Prediction.id == latest_ids.c.id)
            .where(Prediction.upset_score >= min_score)
            .order_by(Prediction.upset_score.desc())
            .limit(50)
        )
    ).scalars().all()

    upsets = []
    for pred in preds:
        fight = await session.get(Fight, pred.fight_id)
        if not fight:
            continue
        f1 = await session.get(Fighter, fight.fighter_1_id)
        f2 = await session.get(Fighter, fight.fighter_2_id)
        event = await session.get(Event, fight.event_id)

        upsets.append(UpsetOut(
            fight_id=pred.fight_id,
            fighter_1_name=f1.name if f1 else "Unknown",
            fighter_2_name=f2.name if f2 else "Unknown",
            event_name=event.name if event else "Unknown",
            fighter_1_win_prob=pred.fighter_1_win_prob,
            fighter_2_win_prob=pred.fighter_2_win_prob,
            upset_score=pred.upset_score,
            betting_confidence=pred.betting_confidence,
        ))

    return upsets


@router.get("/value-bets", response_model=list[ValueBetOut])
async def get_value_bets(
    session: AsyncSession = Depends(get_session),
):
    """Get upcoming fights where the AI sees value (edge >= 3% over Vegas odds)."""
    today = date.today()

    # Get upcoming fights with predictions and odds in a single query
    result = await session.execute(
        select(Fight, Prediction, BettingOdds, Fighter, Event)
        .join(Event, Fight.event_id == Event.id)
        .join(Prediction, Prediction.fight_id == Fight.id)
        .join(BettingOdds, BettingOdds.fight_id == Fight.id)
        .join(Fighter, Fighter.id == Fight.fighter_1_id)
        .where(Event.date >= today)
        .where(Fight.winner_id.is_(None))
    )
    rows = result.all()

    # Deduplicate: keep latest prediction and latest odds per fight
    fight_data: dict[int, dict] = {}
    for fight, pred, odds, f1, event in rows:
        fid = fight.id
        if fid not in fight_data:
            fight_data[fid] = {"fight": fight, "pred": pred, "odds": odds, "event": event}
        else:
            if pred.id > fight_data[fid]["pred"].id:
                fight_data[fid]["pred"] = pred
            if odds.retrieved_at > fight_data[fid]["odds"].retrieved_at:
                fight_data[fid]["odds"] = odds

    value_bets = []
    for fid, d in fight_data.items():
        fight, pred, odds, event = d["fight"], d["pred"], d["odds"], d["event"]
        f1 = await session.get(Fighter, fight.fighter_1_id)
        f2 = await session.get(Fighter, fight.fighter_2_id)

        implied_f1 = 1.0 / odds.fighter_1_decimal if odds.fighter_1_decimal > 0 else 0
        implied_f2 = 1.0 / odds.fighter_2_decimal if odds.fighter_2_decimal > 0 else 0
        edge_f1 = pred.fighter_1_win_prob - implied_f1
        edge_f2 = pred.fighter_2_win_prob - implied_f2
        best_edge = max(edge_f1, edge_f2)

        if best_edge < 0.03:
            continue

        if edge_f1 > edge_f2:
            bet_on = f1.name if f1 else "Unknown"
            american = odds.fighter_1_american
            decimal = odds.fighter_1_decimal
            ai_prob = pred.fighter_1_win_prob
            vegas_implied = implied_f1
        else:
            bet_on = f2.name if f2 else "Unknown"
            american = odds.fighter_2_american
            decimal = odds.fighter_2_decimal
            ai_prob = pred.fighter_2_win_prob
            vegas_implied = implied_f2

        bet_amount = min(100 * (best_edge / 0.05), 500)

        value_bets.append(ValueBetOut(
            fight_id=pred.fight_id,
            fighter_1_name=f1.name if f1 else "Unknown",
            fighter_2_name=f2.name if f2 else "Unknown",
            event_name=event.name if event else "Unknown",
            event_date=str(event.date) if event else "",
            fighter_1_win_prob=pred.fighter_1_win_prob,
            fighter_2_win_prob=pred.fighter_2_win_prob,
            bet_on=bet_on,
            edge=round(best_edge, 4),
            bet_amount=round(bet_amount, 2),
            american_odds=american,
            decimal_odds=round(decimal, 2),
            vegas_implied=round(vegas_implied, 4),
            ai_prob=round(ai_prob, 4),
        ))

    value_bets.sort(key=lambda x: x.edge, reverse=True)
    return value_bets[:50]


@router.get("/bet-history", response_model=list[BetHistoryOut])
async def get_bet_history(
    session: AsyncSession = Depends(get_session),
):
    """Get full bet history: all value bets (past and upcoming) with outcomes."""
    # Latest prediction per fight
    latest_ids = (
        select(func.max(Prediction.id).label("id"))
        .group_by(Prediction.fight_id)
        .subquery()
    )
    preds = (
        await session.execute(
            select(Prediction)
            .join(latest_ids, Prediction.id == latest_ids.c.id)
        )
    ).scalars().all()

    history = []
    for pred in preds:
        fight = await session.get(Fight, pred.fight_id)
        if not fight:
            continue

        # Get odds
        odds_result = await session.execute(
            select(BettingOdds)
            .where(BettingOdds.fight_id == fight.id)
            .order_by(BettingOdds.retrieved_at.desc())
            .limit(1)
        )
        odds = odds_result.scalars().first()
        if not odds:
            continue

        f1 = await session.get(Fighter, fight.fighter_1_id)
        f2 = await session.get(Fighter, fight.fighter_2_id)
        event = await session.get(Event, fight.event_id)

        implied_f1 = 1.0 / odds.fighter_1_decimal if odds.fighter_1_decimal > 0 else 0
        implied_f2 = 1.0 / odds.fighter_2_decimal if odds.fighter_2_decimal > 0 else 0
        edge_f1 = pred.fighter_1_win_prob - implied_f1
        edge_f2 = pred.fighter_2_win_prob - implied_f2
        best_edge = max(edge_f1, edge_f2)

        if best_edge < 0.03:
            continue

        if edge_f1 > edge_f2:
            bet_on = f1.name if f1 else "Unknown"
            american = odds.fighter_1_american
            decimal = odds.fighter_1_decimal
            ai_prob = pred.fighter_1_win_prob
            vegas_implied = implied_f1
        else:
            bet_on = f2.name if f2 else "Unknown"
            american = odds.fighter_2_american
            decimal = odds.fighter_2_decimal
            ai_prob = pred.fighter_2_win_prob
            vegas_implied = implied_f2

        bet_amount = round(min(100 * (best_edge / 0.05), 500), 2)

        # Determine outcome
        winner_name: str | None = None
        won: bool | None = None
        payout: float | None = None

        if fight.winner_id:
            winner = await session.get(Fighter, fight.winner_id)
            winner_name = winner.name if winner else None
            if winner_name:
                won = bet_on == winner_name
                payout = round(bet_amount * (decimal - 1), 2) if won else round(-bet_amount, 2)
        elif fight.result and fight.result.lower() in ("draw", "nc", "no contest"):
            winner_name = None
            won = False
            payout = round(-bet_amount, 2)

        history.append(BetHistoryOut(
            fight_id=pred.fight_id,
            fighter_1_name=f1.name if f1 else "Unknown",
            fighter_2_name=f2.name if f2 else "Unknown",
            event_name=event.name if event else "Unknown",
            event_date=str(event.date) if event else "",
            weight_class=fight.weight_class,
            bet_on=bet_on,
            edge=round(best_edge, 4),
            bet_amount=bet_amount,
            american_odds=american,
            decimal_odds=round(decimal, 2),
            vegas_implied=round(vegas_implied, 4),
            ai_prob=round(ai_prob, 4),
            winner_name=winner_name,
            won=won,
            payout=payout,
        ))

    # Sort by event date descending (newest first)
    history.sort(key=lambda x: x.event_date, reverse=True)
    return history
