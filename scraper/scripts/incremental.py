"""Run an incremental scrape — only fetch events not already in the database."""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from scraper.storage import Storage
from scraper.ufcstats import UFCStatsScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    db_url = os.getenv("DATABASE_URL_SYNC", "postgresql://neuralfight:neuralfight@localhost:5432/neuralfight")
    storage = Storage(db_url)
    known_hashes = storage.get_known_event_hashes()
    logger.info(f"Database has {len(known_hashes)} events already")

    scraper = UFCStatsScraper()
    try:
        async for event, fighters in scraper.scrape_incremental(known_hashes):
            storage.store_fighters(fighters)
            storage.store_event(event)
    finally:
        await scraper.close()

    logger.info("Incremental scrape complete!")


if __name__ == "__main__":
    asyncio.run(main())
