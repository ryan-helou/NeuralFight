import asyncio
import logging
from datetime import date

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import SyncSessionLocal
from app.models import Event, Fight, Prediction
from app.routers import events, fighters, fights, odds, performance, predictions
from app.services.bestfightodds_scraper import fetch_and_store_odds
from app.services.prediction_service import PredictionService
from app.services.results_updater import update_results

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 4 * 3600  # 4 hours


async def _refresh_loop():
    """Background task: refresh odds + generate/update predictions every 4 hours."""
    while True:
        try:
            session = SyncSessionLocal()
            try:
                # 1. Update results from UFCStats for recent events
                results_updated = update_results(session)
                if results_updated:
                    logger.info(f"Results update: {results_updated} fights updated")

                # 2. Refresh odds from BestFightOdds
                count = fetch_and_store_odds(session)
                logger.info(f"Odds refresh: updated {count} fights")

                # 3. Generate predictions for upcoming fights without one
                upcoming_fights = session.execute(
                    select(Fight)
                    .join(Event, Fight.event_id == Event.id)
                    .where(Event.date >= date.today())
                ).scalars().all()

                service = PredictionService(session)
                generated = 0
                for fight in upcoming_fights:
                    existing = session.execute(
                        select(Prediction)
                        .where(Prediction.fight_id == fight.id)
                        .limit(1)
                    ).scalar_one_or_none()
                    if not existing:
                        try:
                            pred = service.generate_prediction(fight.id)
                            if pred:
                                generated += 1
                        except Exception:
                            continue

                logger.info(
                    f"Prediction refresh: {generated} new predictions for "
                    f"{len(upcoming_fights)} upcoming fights"
                )
            except Exception:
                logger.exception("Scheduled refresh failed")
                session.rollback()
            finally:
                session.close()
        except Exception:
            logger.exception("Unexpected error in refresh loop")

        await asyncio.sleep(REFRESH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background refresh
    task = asyncio.create_task(_refresh_loop())
    logger.info("Started 4-hour odds + predictions refresh background task")
    yield
    # Shutdown: cancel background task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="NeuralFight",
    version="0.1.0",
    description="AI-powered UFC fight predictor",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(fighters.router)
app.include_router(fights.router)
app.include_router(odds.router)
app.include_router(predictions.router)
app.include_router(performance.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
