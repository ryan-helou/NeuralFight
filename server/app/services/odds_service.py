"""Betting odds integration via The Odds API."""

import logging

import httpx
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.upset_detector import decimal_to_american
from app.models import BettingOdds, Fight, Fighter

logger = logging.getLogger(__name__)

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds"


async def fetch_and_store_odds(session: Session):
    """Fetch current MMA odds from The Odds API and store them."""
    if not settings.the_odds_api_key:
        logger.warning("THE_ODDS_API_KEY not set, skipping odds fetch")
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(
            ODDS_API_URL,
            params={
                "apiKey": settings.the_odds_api_key,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
        )
        response.raise_for_status()
        data = response.json()

    logger.info(f"Fetched odds for {len(data)} matchups")

    for matchup in data:
        home = matchup.get("home_team", "")
        away = matchup.get("away_team", "")

        # Average odds across bookmakers
        f1_odds_list = []
        f2_odds_list = []
        for bookmaker in matchup.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    if outcome["name"] == home:
                        f1_odds_list.append(outcome["price"])
                    elif outcome["name"] == away:
                        f2_odds_list.append(outcome["price"])

        if not f1_odds_list or not f2_odds_list:
            continue

        f1_decimal = sum(f1_odds_list) / len(f1_odds_list)
        f2_decimal = sum(f2_odds_list) / len(f2_odds_list)

        # Match fighters to database
        f1_id = _fuzzy_match_fighter(session, home)
        f2_id = _fuzzy_match_fighter(session, away)
        if not f1_id or not f2_id:
            logger.warning(f"Could not match fighters: {home} vs {away}")
            continue

        # Find the fight
        fight = session.execute(
            select(Fight).where(
                ((Fight.fighter_1_id == f1_id) & (Fight.fighter_2_id == f2_id))
                | ((Fight.fighter_1_id == f2_id) & (Fight.fighter_2_id == f1_id))
            )
        ).scalar_one_or_none()

        if not fight:
            logger.warning(f"No fight found for {home} vs {away}")
            continue

        # Ensure odds are aligned to fighter_1/fighter_2 order
        if fight.fighter_1_id == f2_id:
            f1_decimal, f2_decimal = f2_decimal, f1_decimal

        odds = BettingOdds(
            fight_id=fight.id,
            source="the_odds_api",
            fighter_1_decimal=round(f1_decimal, 3),
            fighter_2_decimal=round(f2_decimal, 3),
            fighter_1_american=decimal_to_american(f1_decimal),
            fighter_2_american=decimal_to_american(f2_decimal),
        )
        session.add(odds)

    session.commit()
    logger.info("Odds stored successfully")


def _fuzzy_match_fighter(session: Session, name: str) -> int | None:
    """Match a fighter name from The Odds API to the database using fuzzy matching."""
    # First try exact match
    fighter = session.execute(
        select(Fighter).where(Fighter.name == name)
    ).scalar_one_or_none()

    if fighter:
        return fighter.id

    # Fuzzy match against all fighters
    all_fighters = session.execute(select(Fighter.id, Fighter.name)).all()
    best_match = None
    best_score = 0

    for fid, fname in all_fighters:
        score = fuzz.ratio(name.lower(), fname.lower())
        if score > best_score:
            best_score = score
            best_match = fid

    if best_score >= 85:
        return best_match

    return None
