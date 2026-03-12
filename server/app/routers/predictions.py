from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database import get_session, get_sync_session
from app.models import Event, Fight, Fighter, Prediction
from app.schemas.prediction import PredictionOut, UpsetOut
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
    preds = (
        await session.execute(
            select(Prediction)
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
