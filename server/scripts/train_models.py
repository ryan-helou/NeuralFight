"""Script to train all ML models from the database."""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ml.features import FeatureBuilder
from app.ml.training import train_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / ".cache"
FEATURES_CACHE = CACHE_DIR / "features.parquet"
TARGETS_CACHE = CACHE_DIR / "targets.parquet"


def main():
    db_url = os.getenv("DATABASE_URL_SYNC", "postgresql://neuralfight:neuralfight@localhost:5432/neuralfight")

    # Check for cached feature matrix
    if FEATURES_CACHE.exists() and TARGETS_CACHE.exists():
        logger.info("Loading cached feature matrix...")
        features_df = pd.read_parquet(FEATURES_CACHE)
        targets_df = pd.read_parquet(TARGETS_CACHE)
        logger.info(f"Loaded {len(features_df)} samples with {len(features_df.columns)} features from cache")
    else:
        engine = create_engine(db_url)
        with Session(engine) as session:
            logger.info("Building feature matrix (this takes ~40 min)...")
            builder = FeatureBuilder(session)
            features_df, targets_df = builder.build_training_set()
            logger.info(f"Built {len(features_df)} training samples with {len(features_df.columns)} features")

            # Cache to disk immediately so we never rebuild
            CACHE_DIR.mkdir(exist_ok=True)
            features_df.to_parquet(FEATURES_CACHE)
            targets_df.to_parquet(TARGETS_CACHE)
            logger.info(f"Cached feature matrix to {CACHE_DIR}")

    if len(features_df) < 100:
        logger.error("Not enough training data. Run the scraper first.")
        return

    logger.info("Starting model training (this may take a while)...")
    train_all(features_df, targets_df, n_trials=50)
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
