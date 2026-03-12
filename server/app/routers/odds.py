import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, SyncSessionLocal
from app.models import BettingOdds, Fight, Fighter
from app.schemas.odds import OddsOut
from app.services.bestfightodds_scraper import fetch_and_store_odds

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/odds", tags=["odds"])


@router.get("/fight/{fight_id}", response_model=OddsOut | None)
async def get_odds(fight_id: int, session: AsyncSession = Depends(get_session)):
    """Get the latest betting odds for a fight."""
    result = await session.execute(
        select(BettingOdds)
        .where(BettingOdds.fight_id == fight_id)
        .order_by(BettingOdds.retrieved_at.desc())
        .limit(1)
    )
    odds = result.scalars().first()
    if not odds:
        return None

    fight = await session.get(Fight, fight_id)
    f1 = await session.get(Fighter, fight.fighter_1_id) if fight else None
    f2 = await session.get(Fighter, fight.fighter_2_id) if fight else None

    return OddsOut(
        fight_id=odds.fight_id,
        source=odds.source,
        fighter_1_name=f1.name if f1 else "Unknown",
        fighter_2_name=f2.name if f2 else "Unknown",
        fighter_1_decimal=odds.fighter_1_decimal,
        fighter_2_decimal=odds.fighter_2_decimal,
        fighter_1_american=odds.fighter_1_american,
        fighter_2_american=odds.fighter_2_american,
        fighter_1_implied=round(1 / odds.fighter_1_decimal, 4) if odds.fighter_1_decimal > 0 else 0,
        fighter_2_implied=round(1 / odds.fighter_2_decimal, 4) if odds.fighter_2_decimal > 0 else 0,
        retrieved_at=odds.retrieved_at.isoformat(),
    )


@router.post("/refresh")
def refresh_odds():
    """Scrape latest UFC odds from BestFightOdds and store them."""
    session = SyncSessionLocal()
    try:
        count = fetch_and_store_odds(session)
        return {"status": "ok", "fights_updated": count}
    except Exception:
        logger.exception("Failed to refresh odds")
        session.rollback()
        raise
    finally:
        session.close()
