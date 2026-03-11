"""Run a full historical scrape of all UFC events from ufcstats.com."""

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
    scraper = UFCStatsScraper()

    try:
        async for event, fighters in scraper.scrape_full():
            # Store fighters first (so fight FK lookups work)
            storage.store_fighters(fighters)
            # Store event with fights and round stats
            storage.store_event(event)
    finally:
        await scraper.close()

    logger.info("Full scrape complete!")


if __name__ == "__main__":
    asyncio.run(main())
