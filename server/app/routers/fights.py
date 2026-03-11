from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Event, Fight, Fighter, RoundStats
from app.schemas.fight import FightDetailOut, RoundStatsOut

router = APIRouter(prefix="/api/fights", tags=["fights"])


@router.get("/{fight_id}", response_model=FightDetailOut)
async def get_fight(fight_id: int, session: AsyncSession = Depends(get_session)):
    fight = await session.get(Fight, fight_id)
    if not fight:
        raise HTTPException(404, "Fight not found")

    event = await session.get(Event, fight.event_id)
    f1 = await session.get(Fighter, fight.fighter_1_id)
    f2 = await session.get(Fighter, fight.fighter_2_id)
    winner = await session.get(Fighter, fight.winner_id) if fight.winner_id else None

    # Get round stats for each fighter
    f1_rounds_result = await session.execute(
        select(RoundStats)
        .where(RoundStats.fight_id == fight_id, RoundStats.fighter_id == fight.fighter_1_id)
        .order_by(RoundStats.round_number)
    )
    f2_rounds_result = await session.execute(
        select(RoundStats)
        .where(RoundStats.fight_id == fight_id, RoundStats.fighter_id == fight.fighter_2_id)
        .order_by(RoundStats.round_number)
    )

    return FightDetailOut(
        id=fight.id,
        event_name=event.name if event else "Unknown",
        fighter_1=f1,
        fighter_2=f2,
        winner_name=winner.name if winner else None,
        weight_class=fight.weight_class,
        is_title_bout=fight.is_title_bout,
        method=fight.method,
        method_category=fight.method_category,
        finish_round=fight.finish_round,
        finish_time=fight.finish_time,
        total_rounds=fight.total_rounds,
        referee=fight.referee,
        result=fight.result,
        fighter_1_rounds=[RoundStatsOut.model_validate(r) for r in f1_rounds_result.scalars()],
        fighter_2_rounds=[RoundStatsOut.model_validate(r) for r in f2_rounds_result.scalars()],
    )
