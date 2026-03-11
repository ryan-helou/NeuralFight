"""Parse event list and event detail pages from ufcstats.com."""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from scraper.models import ScrapedEvent


def parse_event_list(html: str) -> list[dict]:
    """Parse the completed events list page. Returns list of {name, date, url, hash}."""
    soup = BeautifulSoup(html, "lxml")
    events = []

    rows = soup.select("tr.b-statistics__table-row")
    for row in rows:
        link = row.select_one("a.b-link")
        if not link:
            continue

        url = link["href"].strip()
        name = link.get_text(strip=True)
        hash_id = url.rstrip("/").split("/")[-1]

        date_cell = row.select_one("td.b-statistics__table-col span.b-statistics__date")
        event_date = None
        if date_cell:
            date_text = date_cell.get_text(strip=True)
            try:
                event_date = datetime.strptime(date_text, "%B %d, %Y").date()
            except ValueError:
                pass

        events.append({
            "name": name,
            "date": event_date,
            "url": url,
            "hash": hash_id,
        })

    return events


def parse_event_detail(html: str, event_hash: str) -> ScrapedEvent:
    """Parse an event detail page. Returns event with fight stubs (no round stats yet)."""
    soup = BeautifulSoup(html, "lxml")

    # Event name and date from header
    title_el = soup.select_one("h2.b-content__title span")
    name = title_el.get_text(strip=True) if title_el else "Unknown Event"

    info_items = soup.select("li.b-list__box-list-item")
    event_date = None
    location = None
    for item in info_items:
        text = item.get_text(strip=True)
        if text.startswith("Date:"):
            date_str = text.replace("Date:", "").strip()
            try:
                event_date = datetime.strptime(date_str, "%B %d, %Y").date()
            except ValueError:
                pass
        elif text.startswith("Location:"):
            location = text.replace("Location:", "").strip()

    # Parse fight rows
    fight_rows = soup.select("tr.b-fight-details__table-row.b-fight-details__table-row__hover")
    fights = []
    for i, row in enumerate(fight_rows):
        fight_link = row.get("data-link", "")
        if not fight_link:
            continue

        fight_hash = fight_link.strip().rstrip("/").split("/")[-1]
        cols = row.select("td.b-fight-details__table-col")
        if len(cols) < 8:
            continue

        # Fighter names (column 2 has both fighters as <p> tags)
        fighter_links = cols[1].select("a.b-link")
        if len(fighter_links) < 2:
            continue

        f1_name = fighter_links[0].get_text(strip=True)
        f1_url = fighter_links[0]["href"].strip()
        f1_hash = f1_url.rstrip("/").split("/")[-1]

        f2_name = fighter_links[1].get_text(strip=True)
        f2_url = fighter_links[1]["href"].strip()
        f2_hash = f2_url.rstrip("/").split("/")[-1]

        # Result (first column)
        result_text = cols[0].select_one("p")
        win_indicator = result_text.get_text(strip=True) if result_text else ""
        winner_name = f1_name if win_indicator.lower() == "win" else None

        # Weight class (column 7)
        weight_class_el = cols[6].select_one("p")
        weight_class = weight_class_el.get_text(strip=True) if weight_class_el else None
        is_title = bool(weight_class and "Title" in weight_class)

        # Method (column 8)
        method_el = cols[7].select_one("p")
        method_text = method_el.get_text(strip=True) if method_el else None
        method_category = _categorize_method(method_text) if method_text else None

        # Round (column 9)
        round_el = cols[8].select_one("p") if len(cols) > 8 else None
        finish_round = None
        if round_el:
            try:
                finish_round = int(round_el.get_text(strip=True))
            except ValueError:
                pass

        # Time (column 10)
        time_el = cols[9].select_one("p") if len(cols) > 9 else None
        finish_time = time_el.get_text(strip=True) if time_el else None

        result = "win" if winner_name else "draw"
        if method_text and "nc" in method_text.lower():
            result = "nc"
        elif method_text and "dq" in method_text.lower():
            result = "dq"

        fights.append({
            "ufcstats_hash": fight_hash,
            "fighter_1_name": f1_name,
            "fighter_1_hash": f1_hash,
            "fighter_2_name": f2_name,
            "fighter_2_hash": f2_hash,
            "winner_name": winner_name,
            "weight_class": weight_class,
            "is_title_bout": is_title,
            "method": method_text,
            "method_category": method_category,
            "finish_round": finish_round,
            "finish_time": finish_time,
            "result": result,
            "bout_order": len(fight_rows) - i,  # Main event = highest number
        })

    from scraper.models import ScrapedFight
    event = ScrapedEvent(
        name=name,
        date=event_date or datetime(2000, 1, 1).date(),
        location=location,
        ufcstats_hash=event_hash,
        fights=[ScrapedFight(**f) for f in fights],
    )
    return event


def _categorize_method(method: str) -> str:
    """Categorize a method string into ko_tko, submission, or decision."""
    method_lower = method.lower()
    if "ko" in method_lower or "tko" in method_lower:
        return "ko_tko"
    elif "sub" in method_lower:
        return "submission"
    elif "dec" in method_lower:
        return "decision"
    elif "draw" in method_lower:
        return "draw"
    else:
        return "other"
