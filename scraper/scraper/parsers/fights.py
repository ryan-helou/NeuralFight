"""Parse fight detail pages from ufcstats.com for round-by-round stats."""

import re

from bs4 import BeautifulSoup

from scraper.models import ScrapedRoundStats


def parse_fight_detail(html: str) -> dict:
    """Parse a fight detail page. Returns fight metadata and round-by-round stats.

    Returns:
        {
            "referee": str,
            "total_rounds": int,
            "round_stats": list[ScrapedRoundStats],
        }
    """
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

    # Parse the totals and significant strikes tables
    # There are two main stat tables: "Totals" and "Significant Strikes"
    tables = soup.select("table.b-fight-details__table")

    round_data = {}  # {round_num: {fighter_idx: {stats}}}

    if len(tables) >= 1:
        _parse_totals_table(tables[0], fighters, round_data)
    if len(tables) >= 2:
        _parse_sig_strikes_table(tables[1], fighters, round_data)

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


def _parse_totals_table(table, fighters: list[dict], round_data: dict):
    """Parse the 'Totals' stats table.

    The table has sections per round. Each section has 2 rows (one per fighter).
    Columns: Fighter | KD | Sig.str. | Sig.str.% | Total str. | Td | Td% | Sub.att | Rev. | Ctrl
    """
    body = table.select_one("tbody")
    if not body:
        return

    rows = body.select("tr.b-fight-details__table-row")
    if not rows:
        return

    # Rows come in pairs per round. First pair is "Totals" (aggregate),
    # then per-round sections. The sections are separated by thead rows.
    # We parse per-round rows which are inside tbody sections.
    sections = table.select("tbody")

    for section_idx, section in enumerate(sections):
        rows = section.select("tr.b-fight-details__table-row")
        # Each section has pairs of rows for the two fighters
        # section_idx 0 = totals, 1+ = per round
        round_num = section_idx  # 0 = totals, we skip it

        for row_idx, row in enumerate(rows):
            if round_num == 0:
                continue  # Skip the totals section

            fighter_idx = row_idx % 2
            if round_num not in round_data:
                round_data[round_num] = {}
            if fighter_idx not in round_data[round_num]:
                round_data[round_num][fighter_idx] = {}

            cols = row.select("td.b-fight-details__table-col")
            if len(cols) < 10:
                continue

            stats = round_data[round_num][fighter_idx]
            stats["knockdowns"] = _parse_int(cols[1])
            sig_landed, sig_att = _parse_of(cols[2])
            stats["sig_strikes_landed"] = sig_landed
            stats["sig_strikes_attempted"] = sig_att
            total_landed, total_att = _parse_of(cols[4])
            stats["total_strikes_landed"] = total_landed
            stats["total_strikes_attempted"] = total_att
            td_landed, td_att = _parse_of(cols[5])
            stats["takedowns_landed"] = td_landed
            stats["takedowns_attempted"] = td_att
            stats["submissions_attempted"] = _parse_int(cols[7])
            stats["reversals"] = _parse_int(cols[8])
            stats["control_time_seconds"] = _parse_control_time(cols[9])


def _parse_sig_strikes_table(table, fighters: list[dict], round_data: dict):
    """Parse the 'Significant Strikes' breakdown table.

    Columns: Fighter | Sig.str. | Sig.str.% | Head | Body | Leg | Distance | Clinch | Ground
    """
    sections = table.select("tbody")

    for section_idx, section in enumerate(sections):
        rows = section.select("tr.b-fight-details__table-row")
        round_num = section_idx

        for row_idx, row in enumerate(rows):
            if round_num == 0:
                continue

            fighter_idx = row_idx % 2
            if round_num not in round_data:
                round_data[round_num] = {}
            if fighter_idx not in round_data[round_num]:
                round_data[round_num][fighter_idx] = {}

            cols = row.select("td.b-fight-details__table-col")
            if len(cols) < 9:
                continue

            stats = round_data[round_num][fighter_idx]
            head_l, head_a = _parse_of(cols[3])
            stats["head_strikes_landed"] = head_l
            stats["head_strikes_attempted"] = head_a
            body_l, body_a = _parse_of(cols[4])
            stats["body_strikes_landed"] = body_l
            stats["body_strikes_attempted"] = body_a
            leg_l, leg_a = _parse_of(cols[5])
            stats["leg_strikes_landed"] = leg_l
            stats["leg_strikes_attempted"] = leg_a
            dist_l, dist_a = _parse_of(cols[6])
            stats["distance_strikes_landed"] = dist_l
            stats["distance_strikes_attempted"] = dist_a
            clinch_l, clinch_a = _parse_of(cols[7])
            stats["clinch_strikes_landed"] = clinch_l
            stats["clinch_strikes_attempted"] = clinch_a
            ground_l, ground_a = _parse_of(cols[8])
            stats["ground_strikes_landed"] = ground_l
            stats["ground_strikes_attempted"] = ground_a


def _parse_int(col) -> int:
    """Extract an integer from a table cell."""
    text = col.get_text(strip=True)
    # Handle cases where there are multiple <p> tags (one per fighter in a row)
    p_tags = col.select("p")
    if p_tags:
        text = p_tags[0].get_text(strip=True)
    try:
        return int(text)
    except (ValueError, TypeError):
        return 0


def _parse_of(col) -> tuple[int, int]:
    """Parse 'X of Y' format (e.g., '52 of 103'). Returns (landed, attempted)."""
    text = col.get_text(strip=True)
    p_tags = col.select("p")
    if p_tags:
        text = p_tags[0].get_text(strip=True)
    match = re.search(r"(\d+)\s*of\s*(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def _parse_control_time(col) -> int:
    """Parse control time in 'M:SS' format to total seconds."""
    text = col.get_text(strip=True)
    p_tags = col.select("p")
    if p_tags:
        text = p_tags[0].get_text(strip=True)
    match = re.search(r"(\d+):(\d+)", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return 0
