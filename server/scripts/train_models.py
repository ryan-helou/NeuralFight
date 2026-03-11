"""Script to train all ML models from the database."""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ml.features import FeatureBuilder
from app.ml.training import train_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    db_url = os.getenv("DATABASE_URL_SYNC", "postgresql://neuralfight:neuralfight@localhost:5432/neuralfight")
    engine = create_engine(db_url)

    with Session(engine) as session:
        logger.info("Building feature matrix...")
        builder = FeatureBuilder(session)
        features_df, targets_df = builder.build_training_set()
        logger.info(f"Built {len(features_df)} training samples with {len(features_df.columns)} features")

    if len(features_df) < 100:
        logger.error("Not enough training data. Run the scraper first.")
        return

    logger.info("Starting model training (this may take a while)...")
    train_all(features_df, targets_df, n_trials=50)
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
