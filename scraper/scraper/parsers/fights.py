"""Parse fight detail pages from ufcstats.com for round-by-round stats.

HTML structure: Each table has 1 tbody. Each row = 1 round.
Each cell has 2 <p> tags: first = fighter 1, second = fighter 2.
Row 0 = totals (skipped), rows 1+ = per round.
"""

import re

from bs4 import BeautifulSoup

from scraper.models import ScrapedRoundStats


def parse_fight_detail(html: str) -> dict:
    """Parse a fight detail page. Returns fight metadata and round-by-round stats."""
    soup = BeautifulSoup(html, "lxml")

    # Referee
    referee = None
    detail_items = soup.select("i.b-fight-details__text-item")
    for item in detail_items:
        text = item.get_text(strip=True)
        if "Referee:" in text:
            referee = text.replace("Referee:", "").strip()
            break

    # Get fighter names and hashes from the fight header
    fighter_links = soup.select("a.b-fight-details__person-link")
    if len(fighter_links) < 2:
        return {"referee": referee, "total_rounds": None, "round_stats": []}

    fighters = []
    for link in fighter_links[:2]:
        name = link.get_text(strip=True)
        url = link["href"].strip()
        hash_id = url.rstrip("/").split("/")[-1]
        fighters.append({"name": name, "hash": hash_id})

    tables = soup.select("table.b-fight-details__table")

    # {round_num: {fighter_idx: {stats}}}
    round_data = {}

    if len(tables) >= 1:
        _parse_totals_table(tables[0], round_data)
    if len(tables) >= 2:
        _parse_sig_strikes_table(tables[1], round_data)

    # Build ScrapedRoundStats
    round_stats = []
    total_rounds = 0
    for round_num in sorted(round_data.keys()):
        total_rounds = max(total_rounds, round_num)
        for fighter_idx in [0, 1]:
            stats = round_data[round_num].get(fighter_idx, {})
            round_stats.append(ScrapedRoundStats(
                fighter_name=fighters[fighter_idx]["name"],
                fighter_hash=fighters[fighter_idx]["hash"],
                round_number=round_num,
                knockdowns=stats.get("knockdowns", 0),
                sig_strikes_landed=stats.get("sig_strikes_landed", 0),
                sig_strikes_attempted=stats.get("sig_strikes_attempted", 0),
                total_strikes_landed=stats.get("total_strikes_landed", 0),
                total_strikes_attempted=stats.get("total_strikes_attempted", 0),
                takedowns_landed=stats.get("takedowns_landed", 0),
                takedowns_attempted=stats.get("takedowns_attempted", 0),
                submissions_attempted=stats.get("submissions_attempted", 0),
                reversals=stats.get("reversals", 0),
                control_time_seconds=stats.get("control_time_seconds", 0),
                head_strikes_landed=stats.get("head_strikes_landed", 0),
                head_strikes_attempted=stats.get("head_strikes_attempted", 0),
                body_strikes_landed=stats.get("body_strikes_landed", 0),
                body_strikes_attempted=stats.get("body_strikes_attempted", 0),
                leg_strikes_landed=stats.get("leg_strikes_landed", 0),
                leg_strikes_attempted=stats.get("leg_strikes_attempted", 0),
                distance_strikes_landed=stats.get("distance_strikes_landed", 0),
                distance_strikes_attempted=stats.get("distance_strikes_attempted", 0),
                clinch_strikes_landed=stats.get("clinch_strikes_landed", 0),
                clinch_strikes_attempted=stats.get("clinch_strikes_attempted", 0),
                ground_strikes_landed=stats.get("ground_strikes_landed", 0),
                ground_strikes_attempted=stats.get("ground_strikes_attempted", 0),
            ))

    return {
        "referee": referee,
        "total_rounds": total_rounds if total_rounds > 0 else None,
        "round_stats": round_stats,
    }


def _parse_totals_table(table, round_data: dict):
    """Parse the 'Totals' stats table.

    Each row = 1 round. Each cell has 2 <p> tags (fighter 1, fighter 2).
    Columns: Fighter | KD | Sig.str. | Sig.str.% | Total str. | Td | Td% | Sub.att | Rev. | Ctrl
    Row 0 = totals (skip). Rows 1+ = per round.
    """
    tbody = table.select_one("tbody")
    if not tbody:
        return

    rows = tbody.select("tr.b-fight-details__table-row")

    for row_idx, row in enumerate(rows):
        if row_idx == 0:
            continue  # Skip totals row

        round_num = row_idx
        cols = row.select("td")
        if len(cols) < 10:
            continue

        for fighter_idx in [0, 1]:
            if round_num not in round_data:
                round_data[round_num] = {}
            if fighter_idx not in round_data[round_num]:
                round_data[round_num][fighter_idx] = {}

            stats = round_data[round_num][fighter_idx]
            stats["knockdowns"] = _get_int(cols[1], fighter_idx)
            sig_l, sig_a = _get_of(cols[2], fighter_idx)
            stats["sig_strikes_landed"] = sig_l
            stats["sig_strikes_attempted"] = sig_a
            total_l, total_a = _get_of(cols[4], fighter_idx)
            stats["total_strikes_landed"] = total_l
            stats["total_strikes_attempted"] = total_a
            td_l, td_a = _get_of(cols[5], fighter_idx)
            stats["takedowns_landed"] = td_l
            stats["takedowns_attempted"] = td_a
            stats["submissions_attempted"] = _get_int(cols[7], fighter_idx)
            stats["reversals"] = _get_int(cols[8], fighter_idx)
            stats["control_time_seconds"] = _get_control_time(cols[9], fighter_idx)


def _parse_sig_strikes_table(table, round_data: dict):
    """Parse the 'Significant Strikes' breakdown table.

    Columns: Fighter | Sig.str. | Sig.str.% | Head | Body | Leg | Distance | Clinch | Ground
    Row 0 = totals (skip). Rows 1+ = per round.
    """
    tbody = table.select_one("tbody")
    if not tbody:
        return

    rows = tbody.select("tr.b-fight-details__table-row")

    for row_idx, row in enumerate(rows):
        if row_idx == 0:
            continue

        round_num = row_idx
        cols = row.select("td")
        if len(cols) < 9:
            continue

        for fighter_idx in [0, 1]:
            if round_num not in round_data:
                round_data[round_num] = {}
            if fighter_idx not in round_data[round_num]:
                round_data[round_num][fighter_idx] = {}

            stats = round_data[round_num][fighter_idx]
            head_l, head_a = _get_of(cols[3], fighter_idx)
            stats["head_strikes_landed"] = head_l
            stats["head_strikes_attempted"] = head_a
            body_l, body_a = _get_of(cols[4], fighter_idx)
            stats["body_strikes_landed"] = body_l
            stats["body_strikes_attempted"] = body_a
            leg_l, leg_a = _get_of(cols[5], fighter_idx)
            stats["leg_strikes_landed"] = leg_l
            stats["leg_strikes_attempted"] = leg_a
            dist_l, dist_a = _get_of(cols[6], fighter_idx)
            stats["distance_strikes_landed"] = dist_l
            stats["distance_strikes_attempted"] = dist_a
            clinch_l, clinch_a = _get_of(cols[7], fighter_idx)
            stats["clinch_strikes_landed"] = clinch_l
            stats["clinch_strikes_attempted"] = clinch_a
            ground_l, ground_a = _get_of(cols[8], fighter_idx)
            stats["ground_strikes_landed"] = ground_l
            stats["ground_strikes_attempted"] = ground_a


def _get_p_text(col, fighter_idx: int) -> str:
    """Get the text from the Nth <p> tag in a cell."""
    p_tags = col.select("p")
    if len(p_tags) > fighter_idx:
        return p_tags[fighter_idx].get_text(strip=True)
    return ""


def _get_int(col, fighter_idx: int) -> int:
    """Extract an integer for a specific fighter from a cell."""
    text = _get_p_text(col, fighter_idx)
    try:
        return int(text)
    except (ValueError, TypeError):
        return 0


def _get_of(col, fighter_idx: int) -> tuple[int, int]:
    """Parse 'X of Y' for a specific fighter. Returns (landed, attempted)."""
    text = _get_p_text(col, fighter_idx)
    match = re.search(r"(\d+)\s*of\s*(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def _get_control_time(col, fighter_idx: int) -> int:
    """Parse control time 'M:SS' for a specific fighter to total seconds."""
    text = _get_p_text(col, fighter_idx)
    match = re.search(r"(\d+):(\d+)", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return 0
