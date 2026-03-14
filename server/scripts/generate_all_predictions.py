"""Generate predictions for ALL fights in the database (past + upcoming)."""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Event, Fight
from app.services.prediction_service import PredictionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    db_url = os.getenv(
        "DATABASE_URL_SYNC",
        f"postgresql://{os.environ.get('USER', 'postgres')}@localhost:5432/neuralfight",
    )
    engine = create_engine(db_url)

    with Session(engine) as session:
        # Get ALL fights ordered chronologically
        fights = session.execute(
            select(Fight.id, Event.date, Event.name)
            .join(Event, Fight.event_id == Event.id)
            .order_by(Event.date)
        ).all()

        total = len(fights)
        logger.info(f"Found {total} total fights to process")

        service = PredictionService(session)
        generated = 0
        skipped = 0
        failed = 0

        for i, (fight_id, event_date, event_name) in enumerate(fights):
            try:
                pred = service.get_or_create_prediction(fight_id)
                if pred:
                    generated += 1
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                if failed <= 5:
                    logger.warning(f"Failed fight {fight_id}: {e}")

            if (i + 1) % 500 == 0:
                logger.info(f"Progress: {i+1}/{total} | Generated: {generated} | Skipped: {skipped} | Failed: {failed}")

        logger.info(
            f"Done! Generated: {generated} | Skipped (no history): {skipped} | Failed: {failed} | Total: {total}"
        )


if __name__ == "__main__":
    main()
