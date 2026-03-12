"""Scrapes betting odds from BestFightOdds.com for upcoming UFC events."""

import logging
import re

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BettingOdds, Event, Fight, Fighter

logger = logging.getLogger(__name__)

BASE_URL = "https://www.bestfightodds.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Sportsbook columns in order (matches BFO table headers)
SPORTSBOOKS = [
    "FanDuel", "Caesars", "BetMGM", "BetRivers", "BetWay",
    "Unibet", "DraftKings", "Bet365", "PointsBet",
]


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds."""
    if american > 0:
        return round(1 + american / 100, 4)
    elif american < 0:
        return round(1 + 100 / abs(american), 4)
    return 1.0


def _parse_american_odds(text: str) -> int | None:
    """Parse an American odds string like '+390' or '-590' into an int."""
    text = text.strip().replace("\u2212", "-")  # unicode minus
    match = re.match(r"^([+-]?\d+)$", text)
    if match:
        val = int(match.group(1))
        # Odds like "100" without a sign are even money
        return val if val != 0 else None
    return None


def _fetch_page(url: str) -> BeautifulSoup:
    """Fetch a page and return parsed BeautifulSoup."""
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def scrape_upcoming_ufc_events() -> list[dict]:
    """Scrape the BFO homepage for upcoming UFC event URLs.

    Returns list of dicts with keys: name, url, date.
    """
    soup = _fetch_page(BASE_URL)
    events = []

    for wrapper in soup.select("div.table-outer-wrapper"):
        header = wrapper.select_one(".table-header h1")
        link = wrapper.select_one(".table-header a")
        date_span = wrapper.select_one(".table-header-date")

        if not header or not link:
            continue

        name = header.get_text(strip=True)
        # Only UFC MMA events (skip BJJ, grappling, etc.)
        if "UFC" not in name or "BJJ" in name:
            continue

        events.append({
            "name": name,
            "url": BASE_URL + link["href"],
            "date": date_span.get_text(strip=True) if date_span else "",
        })

    logger.info(f"Found {len(events)} upcoming UFC events on BFO")
    return events


def scrape_event_odds(event_url: str) -> list[dict]:
    """Scrape odds for all fights on a BFO event page.

    Returns list of dicts with keys:
        fighter_1, fighter_2, fighter_1_odds, fighter_2_odds
    where odds are lists of (sportsbook, american_odds) tuples.
    """
    soup = _fetch_page(event_url)

    # Use the non-responsive table (has actual odds data in td cells)
    tables = soup.select("table.odds-table:not(.odds-table-responsive-header)")
    if not tables:
        logger.warning(f"No odds table found at {event_url}")
        return []

    table = tables[0]

    # Parse sportsbook column headers
    header_ths = table.select("thead tr th")
    book_names = [th.get_text(strip=True) for th in header_ths if th.get_text(strip=True)]

    # Collect only fighter rows (rows with <a> links — prop rows have no links)
    fighter_rows = []
    for row in table.select("tbody tr"):
        th = row.select_one("th")
        if th and th.select_one("a"):
            fighter_rows.append(row)

    # Pair consecutive rows into matchups
    matchups = []
    for i in range(0, len(fighter_rows) - 1, 2):
        f1_row = fighter_rows[i]
        f2_row = fighter_rows[i + 1]

        f1_name = f1_row.select_one("th a").get_text(strip=True)
        f2_name = f2_row.select_one("th a").get_text(strip=True)

        f1_odds = _extract_row_odds(f1_row, book_names)
        f2_odds = _extract_row_odds(f2_row, book_names)

        matchups.append({
            "fighter_1": f1_name,
            "fighter_2": f2_name,
            "fighter_1_odds": f1_odds,
            "fighter_2_odds": f2_odds,
        })

    logger.info(f"Parsed {len(matchups)} matchups from {event_url}")
    return matchups


def _extract_row_odds(row, book_names: list[str]) -> list[tuple[str, int]]:
    """Extract (sportsbook, american_odds) pairs from a table row.

    The td cells are ordered to match sportsbook columns. Empty cells and
    non-odds cells (like alert buttons) are skipped.
    """
    tds = row.select("td")
    odds = []
    book_idx = 0

    for td in tds:
        classes = " ".join(td.get("class", []))
        # Skip the alert/button cell at the end
        if "button-cell" in classes:
            continue

        span = td.select_one("span")
        text = span.get_text(strip=True) if span else td.get_text(strip=True)
        parsed = _parse_american_odds(text) if text else None

        if book_idx < len(book_names):
            if parsed is not None:
                odds.append((book_names[book_idx], parsed))
            book_idx += 1

    return odds


def compute_average_odds(odds_list: list[tuple[str, int]]) -> int | None:
    """Average American odds across sportsbooks.

    Averages in decimal space (more accurate) then converts back to American.
    """
    if not odds_list:
        return None

    decimals = [american_to_decimal(am) for _, am in odds_list]
    avg_decimal = sum(decimals) / len(decimals)

    # Convert back to American
    if avg_decimal >= 2.0:
        return round((avg_decimal - 1) * 100)
    elif avg_decimal > 1.0:
        return round(-100 / (avg_decimal - 1))
    return 100


def fetch_and_store_odds(session: Session) -> int:
    """Scrape BestFightOdds for all upcoming UFC events and store odds.

    Returns the number of fights with odds stored.
    """
    events = scrape_upcoming_ufc_events()
    stored = 0

    for event_info in events:
        matchups = scrape_event_odds(event_info["url"])

        for matchup in matchups:
            f1_name = matchup["fighter_1"]
            f2_name = matchup["fighter_2"]

            f1_odds_list = matchup["fighter_1_odds"]
            f2_odds_list = matchup["fighter_2_odds"]

            if not f1_odds_list and not f2_odds_list:
                continue

            # Average odds across sportsbooks
            f1_american = compute_average_odds(f1_odds_list)
            f2_american = compute_average_odds(f2_odds_list)

            if f1_american is None or f2_american is None:
                continue

            f1_decimal = american_to_decimal(f1_american)
            f2_decimal = american_to_decimal(f2_american)

            # Match fighters to our database
            f1_id = _fuzzy_match_fighter(session, f1_name)
            f2_id = _fuzzy_match_fighter(session, f2_name)

            if not f1_id or not f2_id:
                logger.warning(f"Could not match fighters: {f1_name} vs {f2_name}")
                continue

            # Find the fight in our DB (check both orderings)
            fight = session.execute(
                select(Fight).where(
                    ((Fight.fighter_1_id == f1_id) & (Fight.fighter_2_id == f2_id))
                    | ((Fight.fighter_1_id == f2_id) & (Fight.fighter_2_id == f1_id))
                )
            ).scalar_one_or_none()

            if not fight:
                logger.debug(f"No fight found in DB for {f1_name} vs {f2_name}")
                continue

            # Align odds to fight's fighter_1/fighter_2 ordering
            if fight.fighter_1_id == f2_id:
                f1_decimal, f2_decimal = f2_decimal, f1_decimal
                f1_american, f2_american = f2_american, f1_american

            odds = BettingOdds(
                fight_id=fight.id,
                source="bestfightodds",
                fighter_1_decimal=f1_decimal,
                fighter_2_decimal=f2_decimal,
                fighter_1_american=f1_american,
                fighter_2_american=f2_american,
            )
            session.add(odds)
            stored += 1
            logger.info(
                f"Stored odds for {f1_name} vs {f2_name}: "
                f"{f1_american}/{f2_american}"
            )

    session.commit()
    logger.info(f"Stored odds for {stored} fights total")
    return stored


def _fuzzy_match_fighter(session: Session, name: str) -> int | None:
    """Match a BFO fighter name to our database using fuzzy matching."""
    # Exact match first
    fighter = session.execute(
        select(Fighter).where(Fighter.name == name)
    ).scalar_one_or_none()
    if fighter:
        return fighter.id

    # Fuzzy match
    all_fighters = session.execute(select(Fighter.id, Fighter.name)).all()
    best_match = None
    best_score = 0

    for fid, fname in all_fighters:
        score = fuzz.ratio(name.lower(), fname.lower())
        if score > best_score:
            best_score = score
            best_match = fid

    if best_score >= 85:
        logger.debug(f"Fuzzy matched '{name}' → fighter_id={best_match} (score={best_score})")
        return best_match

    logger.debug(f"No match for '{name}' (best score={best_score})")
    return None
