"""Main scraper orchestrator for ufcstats.com."""

import asyncio
import logging

import httpx

from scraper.models import ScrapedEvent, ScrapedFighter
from scraper.parsers.events import parse_event_detail, parse_event_list
from scraper.parsers.fighters import parse_fighter_detail
from scraper.parsers.fights import parse_fight_detail

logger = logging.getLogger(__name__)

BASE_URL = "http://www.ufcstats.com"
EVENTS_LIST_URL = f"{BASE_URL}/statistics/events/completed?page=all"
EVENT_DETAIL_URL = f"{BASE_URL}/event-details/"
FIGHT_DETAIL_URL = f"{BASE_URL}/fight-details/"
FIGHTER_DETAIL_URL = f"{BASE_URL}/fighter-details/"

# Rate limiting: max concurrent requests and delay between batches
MAX_CONCURRENT = 3
REQUEST_DELAY = 1.0  # seconds between requests


class UFCStatsScraper:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "NeuralFight/1.0 (UFC Research Project)"},
            follow_redirects=True,
        )
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def close(self):
        await self.client.aclose()

    async def _fetch(self, url: str) -> str | None:
        """Fetch a URL with rate limiting and error handling."""
        async with self._semaphore:
            try:
                await asyncio.sleep(REQUEST_DELAY)
                response = await self.client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch {url}: {e}")
                return None

    async def scrape_event_list(self) -> list[dict]:
        """Scrape the list of all completed UFC events."""
        logger.info("Scraping event list...")
        html = await self._fetch(EVENTS_LIST_URL)
        if not html:
            return []
        events = parse_event_list(html)
        logger.info(f"Found {len(events)} events")
        return events

    async def scrape_event(self, event_hash: str) -> ScrapedEvent | None:
        """Scrape a single event detail page."""
        url = f"{EVENT_DETAIL_URL}{event_hash}"
        html = await self._fetch(url)
        if not html:
            return None
        return parse_event_detail(html, event_hash)

    async def scrape_fight(self, fight_hash: str) -> dict | None:
        """Scrape round-by-round stats for a single fight."""
        url = f"{FIGHT_DETAIL_URL}{fight_hash}"
        html = await self._fetch(url)
        if not html:
            return None
        return parse_fight_detail(html)

    async def scrape_fighter(self, fighter_hash: str) -> ScrapedFighter | None:
        """Scrape a fighter profile page."""
        url = f"{FIGHTER_DETAIL_URL}{fighter_hash}"
        html = await self._fetch(url)
        if not html:
            return None
        return parse_fighter_detail(html, fighter_hash)

    async def scrape_full(self, progress_callback=None):
        """Run a full scrape of all events, fights, and fighters.

        Yields (event, fights_with_rounds, fighters) tuples as each event completes.
        """
        # Step 1: Get all events
        event_list = await self.scrape_event_list()
        total = len(event_list)
        logger.info(f"Starting full scrape of {total} events")

        seen_fighters = set()
        all_fighters = []

        for idx, event_info in enumerate(event_list):
            event_hash = event_info["hash"]
            logger.info(f"[{idx + 1}/{total}] Scraping event: {event_info['name']}")

            # Step 2: Get event detail (fight list)
            event = await self.scrape_event(event_hash)
            if not event:
                continue

            # Step 3: For each fight, get round-by-round stats
            for fight in event.fights:
                fight_detail = await self.scrape_fight(fight.ufcstats_hash)
                if fight_detail:
                    fight.round_stats = fight_detail["round_stats"]
                    fight.referee = fight_detail.get("referee")
                    fight.total_rounds = fight_detail.get("total_rounds")

                # Collect unique fighter hashes for profile scraping
                for fhash in [fight.fighter_1_hash, fight.fighter_2_hash]:
                    if fhash not in seen_fighters:
                        seen_fighters.add(fhash)
                        fighter = await self.scrape_fighter(fhash)
                        if fighter:
                            all_fighters.append(fighter)

            if progress_callback:
                progress_callback(idx + 1, total, event.name)

            yield event, all_fighters

    async def scrape_incremental(self, known_event_hashes: set[str]):
        """Scrape only events not already in the database."""
        event_list = await self.scrape_event_list()
        new_events = [e for e in event_list if e["hash"] not in known_event_hashes]
        logger.info(f"Found {len(new_events)} new events to scrape")

        seen_fighters = set()
        all_fighters = []

        for event_info in new_events:
            event = await self.scrape_event(event_info["hash"])
            if not event:
                continue

            for fight in event.fights:
                fight_detail = await self.scrape_fight(fight.ufcstats_hash)
                if fight_detail:
                    fight.round_stats = fight_detail["round_stats"]
                    fight.referee = fight_detail.get("referee")
                    fight.total_rounds = fight_detail.get("total_rounds")

                for fhash in [fight.fighter_1_hash, fight.fighter_2_hash]:
                    if fhash not in seen_fighters:
                        seen_fighters.add(fhash)
                        fighter = await self.scrape_fighter(fhash)
                        if fighter:
                            all_fighters.append(fighter)

            yield event, all_fighters
