from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Fighter, Fight, Event, RoundStats
from app.schemas.fighter import FighterFightOut, FighterOut, FighterProfileOut

router = APIRouter(prefix="/api/fighters", tags=["fighters"])


@router.get("", response_model=list[FighterOut])
async def search_fighters(
    q: str = Query(..., min_length=2, description="Search by name"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Fighter)
        .where(Fighter.name.ilike(f"%{q}%"))
        .order_by(Fighter.name)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{fighter_id}", response_model=FighterOut)
async def get_fighter(fighter_id: int, session: AsyncSession = Depends(get_session)):
    fighter = await session.get(Fighter, fighter_id)
    if not fighter:
        raise HTTPException(404, "Fighter not found")
    return fighter


@router.get("/{fighter_id}/profile", response_model=FighterProfileOut)
async def get_fighter_profile(
    fighter_id: int, session: AsyncSession = Depends(get_session)
):
    fighter = await session.get(Fighter, fighter_id)
    if not fighter:
        raise HTTPException(404, "Fighter not found")

    # Get all fights involving this fighter, joined with event
    fights_result = await session.execute(
        select(Fight)
        .join(Event, Fight.event_id == Event.id)
        .where(
            or_(Fight.fighter_1_id == fighter_id, Fight.fighter_2_id == fighter_id)
        )
        .order_by(Event.date.desc())
    )
    fights = fights_result.scalars().all()

    # Compute record
    wins = 0
    losses = 0
    draws = 0
    ko_wins = 0
    sub_wins = 0
    dec_wins = 0

    today = date.today()
    recent_fights: list[FighterFightOut] = []
    upcoming_fights: list[FighterFightOut] = []

    for fight in fights:
        event = fight.event
        is_fighter_1 = fight.fighter_1_id == fighter_id
        opponent = fight.fighter_2 if is_fighter_1 else fight.fighter_1

        if event.date > today and fight.winner_id is None and fight.result is None:
            # Upcoming fight
            upcoming_fights.append(
                FighterFightOut(
                    fight_id=fight.id,
                    event_name=event.name,
                    event_date=event.date.isoformat(),
                    opponent_name=opponent.name,
                    result=None,
                    method=None,
                    weight_class=fight.weight_class,
                    is_title_bout=fight.is_title_bout,
                )
            )
        else:
            # Completed fight - determine result
            if fight.winner_id == fighter_id:
                result_str = "W"
                wins += 1
                cat = (fight.method_category or "").lower()
                if cat in ("ko_tko", "ko", "tko"):
                    ko_wins += 1
                elif cat in ("sub", "submission"):
                    sub_wins += 1
                elif cat in ("dec", "decision"):
                    dec_wins += 1
            elif fight.winner_id is not None:
                result_str = "L"
                losses += 1
            elif fight.result and "draw" in fight.result.lower():
                result_str = "D"
                draws += 1
            elif fight.result and "nc" in fight.result.lower():
                result_str = "NC"
            else:
                result_str = "D"
                draws += 1

            if len(recent_fights) < 10:
                recent_fights.append(
                    FighterFightOut(
                        fight_id=fight.id,
                        event_name=event.name,
                        event_date=event.date.isoformat(),
                        opponent_name=opponent.name,
                        result=result_str,
                        method=fight.method,
                        weight_class=fight.weight_class,
                        is_title_bout=fight.is_title_bout,
                    )
                )

    # Compute career stat averages from round_stats
    stats_result = await session.execute(
        select(
            func.count(func.distinct(RoundStats.fight_id)).label("fight_count"),
            func.sum(RoundStats.sig_strikes_landed).label("total_sig_strikes"),
            func.sum(RoundStats.takedowns_landed).label("total_takedowns"),
            func.sum(RoundStats.knockdowns).label("total_knockdowns"),
            func.sum(RoundStats.control_time_seconds).label("total_control_time"),
            func.sum(RoundStats.submissions_attempted).label("total_sub_attempts"),
        ).where(RoundStats.fighter_id == fighter_id)
    )
    stats_row = stats_result.one()
    fight_count = stats_row.fight_count or 0

    if fight_count > 0:
        avg_sig_strikes = round((stats_row.total_sig_strikes or 0) / fight_count, 1)
        avg_takedowns = round((stats_row.total_takedowns or 0) / fight_count, 1)
        avg_knockdowns = round((stats_row.total_knockdowns or 0) / fight_count, 1)
        avg_control_time = round((stats_row.total_control_time or 0) / fight_count, 1)
        avg_sub_attempts = round((stats_row.total_sub_attempts or 0) / fight_count, 1)
    else:
        avg_sig_strikes = 0.0
        avg_takedowns = 0.0
        avg_knockdowns = 0.0
        avg_control_time = 0.0
        avg_sub_attempts = 0.0

    return FighterProfileOut(
        id=fighter.id,
        name=fighter.name,
        nickname=fighter.nickname,
        height_inches=fighter.height_inches,
        reach_inches=fighter.reach_inches,
        dob=fighter.dob.isoformat() if fighter.dob else None,
        stance=fighter.stance,
        wins=wins,
        losses=losses,
        draws=draws,
        ko_wins=ko_wins,
        sub_wins=sub_wins,
        dec_wins=dec_wins,
        avg_sig_strikes=avg_sig_strikes,
        avg_takedowns=avg_takedowns,
        avg_knockdowns=avg_knockdowns,
        avg_control_time=avg_control_time,
        avg_sub_attempts=avg_sub_attempts,
        recent_fights=recent_fights,
        upcoming_fights=upcoming_fights,
    )
