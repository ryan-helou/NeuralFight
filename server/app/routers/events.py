from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Event, Fight, Fighter, Prediction
from app.models.betting_odds import BettingOdds
from app.schemas.event import EventDetailOut, EventOut, FightSummaryOut

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[EventOut])
async def list_events(
    upcoming: bool = Query(False, description="Only show upcoming events"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    query = select(Event)
    if upcoming:
        query = query.where(Event.date >= date.today())
    query = query.order_by(Event.date.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    events = result.scalars().all()

    out = []
    for event in events:
        fight_count_result = await session.execute(
            select(func.count()).where(Fight.event_id == event.id)
        )
        count = fight_count_result.scalar()
        out.append(EventOut(
            id=event.id,
            name=event.name,
            date=event.date,
            location=event.location,
            fight_count=count,
        ))
    return out


@router.get("/{event_id}", response_model=EventDetailOut)
async def get_event(event_id: int, session: AsyncSession = Depends(get_session)):
    event = await session.get(Event, event_id)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(404, "Event not found")

    fights_result = await session.execute(
        select(Fight).where(Fight.event_id == event_id).order_by(Fight.bout_order.desc())
    )
    fights = fights_result.scalars().all()

    fight_summaries = []
    for fight in fights:
        f1 = await session.get(Fighter, fight.fighter_1_id)
        f2 = await session.get(Fighter, fight.fighter_2_id)
        winner = await session.get(Fighter, fight.winner_id) if fight.winner_id else None

        # Get cached prediction if available
        pred_result = await session.execute(
            select(Prediction).where(Prediction.fight_id == fight.id).order_by(Prediction.created_at.desc())
        )
        pred = pred_result.scalars().first()

        # Get betting odds if available
        odds_result = await session.execute(
            select(BettingOdds).where(BettingOdds.fight_id == fight.id).order_by(BettingOdds.retrieved_at.desc()).limit(1)
        )
        odds = odds_result.scalars().first()
        vegas_f1 = round(1 / odds.fighter_1_decimal, 4) if odds and odds.fighter_1_decimal > 0 else None
        vegas_f2 = round(1 / odds.fighter_2_decimal, 4) if odds and odds.fighter_2_decimal > 0 else None

        # Compute value bet info
        bet_on = None
        bet_amount = None
        bet_decimal_odds = None
        if pred and odds and vegas_f1 is not None and vegas_f2 is not None:
            edge_f1 = pred.fighter_1_win_prob - vegas_f1
            edge_f2 = pred.fighter_2_win_prob - vegas_f2
            best_edge = max(edge_f1, edge_f2)
            if best_edge >= 0.03:
                if edge_f1 > edge_f2:
                    bet_on = f1.name if f1 else "Unknown"
                    bet_decimal_odds = round(odds.fighter_1_decimal, 2)
                else:
                    bet_on = f2.name if f2 else "Unknown"
                    bet_decimal_odds = round(odds.fighter_2_decimal, 2)
                bet_amount = round(min(100 * (best_edge / 0.05), 500), 2)

        fight_summaries.append(FightSummaryOut(
            id=fight.id,
            fighter_1_name=f1.name if f1 else "Unknown",
            fighter_2_name=f2.name if f2 else "Unknown",
            weight_class=fight.weight_class,
            is_title_bout=fight.is_title_bout,
            method=fight.method,
            result=fight.result,
            winner_name=winner.name if winner else None,
            fighter_1_win_prob=pred.fighter_1_win_prob if pred else None,
            fighter_2_win_prob=pred.fighter_2_win_prob if pred else None,
            vegas_fighter_1_implied=vegas_f1,
            vegas_fighter_2_implied=vegas_f2,
            fighter_1_american=odds.fighter_1_american if odds else None,
            fighter_2_american=odds.fighter_2_american if odds else None,
            upset_score=pred.upset_score if pred else None,
            bet_amount=bet_amount,
            bet_on=bet_on,
            bet_decimal_odds=bet_decimal_odds,
        ))

    return EventDetailOut(
        id=event.id,
        name=event.name,
        date=event.date,
        location=event.location,
        fights=fight_summaries,
    )
