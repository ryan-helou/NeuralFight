from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Fighter
from app.schemas.fighter import FighterOut

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
