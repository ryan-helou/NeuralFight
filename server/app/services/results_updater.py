"""Update fight results by scraping UFCStats for recently completed events.

Self-contained — does not depend on the scraper package.
"""

import logging
import time
from datetime import date, datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Fight, Fighter
from app.models.round_stats import RoundStats

logger = logging.getLogger(__name__)

BASE_URL = "http://www.ufcstats.com"
EVENTS_LIST_URL = f"{BASE_URL}/statistics/events/completed?page=all"


def update_results(session: Session) -> int:
    """Scrape UFCStats for results of recently completed events.

    Looks for events in the last 14 days that have fights without results,
    then scrapes UFCStats to fill in winners, methods, and round stats.

    Returns number of fights updated.
    """
    events = _events_needing_results(session)
    if not events:
        logger.info("No events need results updates")
        return 0

    logger.info(f"Found {len(events)} events needing results: {[e.name for e in events]}")

    updated = 0
    try:
        with httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "NeuralFight/1.0"},
            follow_redirects=True,
        ) as client:
            # Get completed events list from UFCStats
            resp = client.get(EVENTS_LIST_URL)
            resp.raise_for_status()
            ufcstats_events = _parse_event_list(resp.text)

            for event in events:
                matched = _find_matching_event(event, ufcstats_events, session)
                if not matched:
                    logger.info(f"Could not find '{event.name}' on UFCStats")
                    continue

                # Scrape event detail page
                time.sleep(0.5)
                resp = client.get(f"{BASE_URL}/event-details/{matched['hash']}")
                if resp.status_code != 200:
                    continue

                scraped_fights = _parse_event_fights(resp.text)
                if not scraped_fights:
                    continue

                # Update event hash if BFO-created
                if event.ufcstats_hash.startswith("bfo-"):
                    event.ufcstats_hash = matched["hash"]

                # Get DB fights for this event
                db_fights = session.execute(
                    select(Fight).where(Fight.event_id == event.id)
                ).scalars().all()

                for sf in scraped_fights:
                    db_fight = _match_fight(session, db_fights, sf)
                    if not db_fight or db_fight.winner_id is not None:
                        continue

                    f1 = session.get(Fighter, db_fight.fighter_1_id)
                    f2 = session.get(Fighter, db_fight.fighter_2_id)

                    # Set winner
                    winner_id = None
                    if sf["winner_name"]:
                        if f1 and _names_match(sf["winner_name"], f1.name):
                            winner_id = f1.id
                        elif f2 and _names_match(sf["winner_name"], f2.name):
                            winner_id = f2.id

                    db_fight.winner_id = winner_id
                    db_fight.method = sf["method"]
                    db_fight.method_category = sf["method_category"]
                    db_fight.finish_round = sf["finish_round"]
                    db_fight.finish_time = sf["finish_time"]
                    db_fight.result = sf["result"]
                    if sf["weight_class"]:
                        db_fight.weight_class = sf["weight_class"]
                    if sf["bout_order"] is not None:
                        db_fight.bout_order = sf["bout_order"]

                    # Scrape round stats for this fight
                    if sf["fight_hash"]:
                        try:
                            time.sleep(0.5)
                            fr = client.get(f"{BASE_URL}/fight-details/{sf['fight_hash']}")
                            if fr.status_code == 200:
                                _store_round_stats(session, db_fight.id, fr.text)
                        except Exception:
                            logger.exception(f"Failed round stats for fight {db_fight.id}")

                    updated += 1
                    logger.info(
                        f"Updated: {f1.name if f1 else '?'} vs {f2.name if f2 else '?'} "
                        f"-> {sf['winner_name']} by {sf['method']}"
                    )

                session.commit()

    except Exception:
        logger.exception("Results update failed")
        session.rollback()

    return updated


# ---------- helpers ----------


def _events_needing_results(session: Session) -> list[Event]:
    cutoff = date.today() + timedelta(days=1)
    lookback = date.today() - timedelta(days=14)

    events = session.execute(
        select(Event).where(Event.date >= lookback, Event.date < cutoff)
    ).scalars().all()

    result = []
    for event in events:
        fights = session.execute(
            select(Fight).where(Fight.event_id == event.id)
        ).scalars().all()
        if any(f.winner_id is None and f.result is None for f in fights):
            result.append(event)
    return result


def _parse_event_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    events = []
    for row in soup.select("tr.b-statistics__table-row"):
        link = row.select_one("a.b-link")
        if not link:
            continue
        url = link["href"].strip()
        name = link.get_text(strip=True)
        hash_id = url.rstrip("/").split("/")[-1]

        # Parse date from the second column
        date_span = row.select_one("span.b-statistics__date")
        event_date = None
        if date_span:
            try:
                event_date = datetime.strptime(date_span.get_text(strip=True), "%B %d, %Y").date()
            except ValueError:
                pass

        events.append({"name": name, "hash": hash_id, "date": event_date})
    return events


def _parse_event_fights(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("tr.b-fight-details__table-row.b-fight-details__table-row__hover")
    fights = []
    total = len(rows)

    for i, row in enumerate(rows):
        fight_link = row.get("data-link", "")
        if not fight_link:
            continue

        fight_hash = fight_link.strip().rstrip("/").split("/")[-1]
        cols = row.select("td.b-fight-details__table-col")
        if len(cols) < 8:
            continue

        fighter_links = cols[1].select("a.b-link")
        if len(fighter_links) < 2:
            continue

        f1_name = fighter_links[0].get_text(strip=True)
        f2_name = fighter_links[1].get_text(strip=True)

        result_p = cols[0].select_one("p")
        win_indicator = result_p.get_text(strip=True) if result_p else ""
        winner_name = f1_name if win_indicator.lower() == "win" else None

        wc_el = cols[6].select_one("p") if len(cols) > 6 else None
        weight_class = wc_el.get_text(strip=True) if wc_el else None

        method_el = cols[7].select_one("p") if len(cols) > 7 else None
        method = method_el.get_text(strip=True) if method_el else None
        method_category = _categorize_method(method) if method else None

        round_el = cols[8].select_one("p") if len(cols) > 8 else None
        finish_round = None
        if round_el:
            try:
                finish_round = int(round_el.get_text(strip=True))
            except ValueError:
                pass

        time_el = cols[9].select_one("p") if len(cols) > 9 else None
        finish_time = time_el.get_text(strip=True) if time_el else None

        result = "win" if winner_name else "draw"
        if method and "nc" in method.lower():
            result = "nc"

        fights.append({
            "fight_hash": fight_hash,
            "fighter_1_name": f1_name,
            "fighter_2_name": f2_name,
            "winner_name": winner_name,
            "weight_class": weight_class,
            "method": method,
            "method_category": method_category,
            "finish_round": finish_round,
            "finish_time": finish_time,
            "result": result,
            "bout_order": total - i,
        })

    return fights


def _store_round_stats(session: Session, fight_id: int, html: str):
    """Parse fight detail page and store round-by-round stats."""
    soup = BeautifulSoup(html, "lxml")

    # Find fighter links to get hashes
    fighter_links = soup.select("h3.b-fight-details__person-name a")
    if len(fighter_links) < 2:
        return

    f1_hash = fighter_links[0]["href"].strip().rstrip("/").split("/")[-1]
    f2_hash = fighter_links[1]["href"].strip().rstrip("/").split("/")[-1]

    # Parse totals and significant strikes tables
    tables = soup.select("table.b-fight-details__table")
    if len(tables) < 2:
        return

    # Each table has per-round rows; first table = totals, second = sig strikes
    totals_body = tables[0].select("tbody tr")
    sig_body = tables[1].select("tbody tr") if len(tables) > 1 else []

    for round_idx, row in enumerate(totals_body):
        round_num = round_idx + 1
        cols = row.select("td")
        if len(cols) < 10:
            continue

        for fighter_idx, f_hash in enumerate([f1_hash, f2_hash]):
            fighter = session.execute(
                select(Fighter).where(Fighter.ufcstats_hash == f_hash)
            ).scalar_one_or_none()
            if not fighter:
                continue

            # Check if already exists
            existing = session.execute(
                select(RoundStats).where(
                    RoundStats.fight_id == fight_id,
                    RoundStats.fighter_id == fighter.id,
                    RoundStats.round_number == round_num,
                )
            ).scalar_one_or_none()
            if existing:
                continue

            # Parse stats from the row — each cell has 2 <p> tags (one per fighter)
            def _get_val(col_idx: int) -> str:
                ps = cols[col_idx].select("p")
                return ps[fighter_idx].get_text(strip=True) if len(ps) > fighter_idx else "0"

            def _parse_of(text: str) -> tuple[int, int]:
                parts = text.split(" of ")
                try:
                    return int(parts[0]), int(parts[1]) if len(parts) > 1 else int(parts[0])
                except (ValueError, IndexError):
                    return 0, 0

            def _parse_int(text: str) -> int:
                try:
                    return int(text)
                except ValueError:
                    return 0

            def _parse_time(text: str) -> int:
                parts = text.split(":")
                try:
                    return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
                except ValueError:
                    return 0

            kd = _parse_int(_get_val(1))
            sig_l, sig_a = _parse_of(_get_val(2))
            tot_l, tot_a = _parse_of(_get_val(4))
            td_l, td_a = _parse_of(_get_val(5))
            sub_att = _parse_int(_get_val(7))
            rev = _parse_int(_get_val(8))
            ctrl = _parse_time(_get_val(9))

            # Sig strikes breakdown from second table
            head_l, head_a, body_l, body_a, leg_l, leg_a = 0, 0, 0, 0, 0, 0
            dist_l, dist_a, clinch_l, clinch_a, ground_l, ground_a = 0, 0, 0, 0, 0, 0

            if round_idx < len(sig_body):
                sig_cols = sig_body[round_idx].select("td")
                if len(sig_cols) >= 9:
                    def _sig_val(ci: int) -> str:
                        ps = sig_cols[ci].select("p")
                        return ps[fighter_idx].get_text(strip=True) if len(ps) > fighter_idx else "0 of 0"

                    head_l, head_a = _parse_of(_sig_val(3))
                    body_l, body_a = _parse_of(_sig_val(4))
                    leg_l, leg_a = _parse_of(_sig_val(5))
                    dist_l, dist_a = _parse_of(_sig_val(6))
                    clinch_l, clinch_a = _parse_of(_sig_val(7))
                    ground_l, ground_a = _parse_of(_sig_val(8))

            session.add(RoundStats(
                fight_id=fight_id,
                fighter_id=fighter.id,
                round_number=round_num,
                knockdowns=kd,
                sig_strikes_landed=sig_l,
                sig_strikes_attempted=sig_a,
                total_strikes_landed=tot_l,
                total_strikes_attempted=tot_a,
                takedowns_landed=td_l,
                takedowns_attempted=td_a,
                submissions_attempted=sub_att,
                reversals=rev,
                control_time_seconds=ctrl,
                head_strikes_landed=head_l,
                head_strikes_attempted=head_a,
                body_strikes_landed=body_l,
                body_strikes_attempted=body_a,
                leg_strikes_landed=leg_l,
                leg_strikes_attempted=leg_a,
                distance_strikes_landed=dist_l,
                distance_strikes_attempted=dist_a,
                clinch_strikes_landed=clinch_l,
                clinch_strikes_attempted=clinch_a,
                ground_strikes_landed=ground_l,
                ground_strikes_attempted=ground_a,
            ))


def _find_matching_event(
    db_event: Event, ufcstats_events: list[dict], session: Session
) -> dict | None:
    """Find a UFCStats event matching our DB event.

    Tries name matching first, then falls back to date matching.
    BFO uses names like "UFC Vegas 114" while UFCStats uses
    "UFC Fight Night: Emmett vs. Vallejos" — so name matching alone fails.
    """
    db_norm = db_event.name.lower().strip()

    for uf in ufcstats_events:
        uf_norm = uf["name"].lower().strip()
        # Exact match
        if db_norm == uf_norm:
            return uf
        # Substring match
        if db_norm in uf_norm or uf_norm in db_norm:
            return uf
        # Numbered event match: "UFC 326" matches "UFC 326: ..."
        db_words = set(db_norm.split())
        uf_words = set(uf_norm.split())
        db_nums = {w for w in db_words if w.isdigit()}
        uf_nums = {w for w in uf_words if w.isdigit()}
        if db_nums and db_nums == uf_nums and ("ufc" in db_words and "ufc" in uf_words):
            return uf

    # Fallback: match by date (BFO "UFC Vegas 114" = UFCStats "UFC Fight Night: ..." on same date)
    if db_event.date:
        for uf in ufcstats_events:
            if uf.get("date") == db_event.date:
                logger.info(
                    f"Matched by date: '{db_event.name}' -> '{uf['name']}' ({db_event.date})"
                )
                return uf

    return None


def _match_fight(session: Session, db_fights: list[Fight], scraped: dict) -> Fight | None:
    for f in db_fights:
        f1 = session.get(Fighter, f.fighter_1_id)
        f2 = session.get(Fighter, f.fighter_2_id)
        if not f1 or not f2:
            continue
        sf1, sf2 = scraped["fighter_1_name"], scraped["fighter_2_name"]
        if (_names_match(f1.name, sf1) and _names_match(f2.name, sf2)) or \
           (_names_match(f1.name, sf2) and _names_match(f2.name, sf1)):
            return f
    return None


def _names_match(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        return s.lower().strip().replace("'", "").replace("-", " ")
    return norm(a) == norm(b)


def _categorize_method(method: str) -> str:
    m = method.lower()
    if "ko" in m or "tko" in m:
        return "ko_tko"
    elif "sub" in m:
        return "submission"
    elif "dec" in m:
        return "decision"
    elif "draw" in m:
        return "draw"
    return "other"
