"""Parse fighter profile pages from ufcstats.com."""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from scraper.models import ScrapedFighter


def parse_fighter_detail(html: str, fighter_hash: str) -> ScrapedFighter:
    """Parse a fighter detail page for physical attributes."""
    soup = BeautifulSoup(html, "lxml")

    # Name
    name_el = soup.select_one("h2.b-content__title span")
    name = name_el.get_text(strip=True) if name_el else "Unknown"

    # Nickname
    nickname_el = soup.select_one("p.b-content__Nickname")
    nickname = nickname_el.get_text(strip=True) if nickname_el else None
    if nickname == "":
        nickname = None

    # Stats from the info box
    info_items = soup.select("li.b-list__box-list-item")
    height_inches = None
    reach_inches = None
    stance = None
    dob = None

    for item in info_items:
        text = item.get_text(strip=True)

        if text.startswith("Height:"):
            height_str = text.replace("Height:", "").strip()
            height_inches = _parse_height(height_str)

        elif text.startswith("Reach:"):
            reach_str = text.replace("Reach:", "").strip().replace('"', "")
            try:
                reach_inches = int(float(reach_str))
            except (ValueError, TypeError):
                pass

        elif text.startswith("STANCE:") or text.startswith("Stance:"):
            stance = text.split(":", 1)[1].strip().lower()
            if stance == "--" or stance == "":
                stance = None

        elif text.startswith("DOB:"):
            dob_str = text.replace("DOB:", "").strip()
            try:
                dob = datetime.strptime(dob_str, "%b %d, %Y").date()
            except ValueError:
                pass

    return ScrapedFighter(
        name=name,
        nickname=nickname,
        ufcstats_hash=fighter_hash,
        height_inches=height_inches,
        reach_inches=reach_inches,
        dob=dob,
        stance=stance,
    )


def _parse_height(height_str: str) -> int | None:
    """Parse height like 5' 11\" to inches."""
    match = re.search(r"(\d+)'\s*(\d+)", height_str)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        return feet * 12 + inches
    return None
