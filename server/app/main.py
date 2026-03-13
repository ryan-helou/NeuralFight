import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SyncSessionLocal
from app.routers import events, fighters, fights, odds, performance, predictions
from app.services.bestfightodds_scraper import fetch_and_store_odds

logger = logging.getLogger(__name__)

ODDS_REFRESH_INTERVAL = 3600  # 1 hour


async def _odds_refresh_loop():
    """Background task that refreshes odds from BestFightOdds every hour."""
    while True:
        try:
            session = SyncSessionLocal()
            try:
                count = fetch_and_store_odds(session)
                logger.info(f"Scheduled odds refresh: updated {count} fights")
            except Exception:
                logger.exception("Scheduled odds refresh failed")
                session.rollback()
            finally:
                session.close()
        except Exception:
            logger.exception("Unexpected error in odds refresh loop")

        await asyncio.sleep(ODDS_REFRESH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background odds refresh
    task = asyncio.create_task(_odds_refresh_loop())
    logger.info("Started hourly odds refresh background task")
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
    allow_origins=["http://localhost:5173"],
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
