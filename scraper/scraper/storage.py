"""Store scraped data into PostgreSQL via SQLAlchemy."""

import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Add server to path so we can import the ORM models
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "server"))

from app.database import Base
from app.models import BettingOdds, Event, Fight, Fighter, Prediction, RoundStats
from scraper.models import ScrapedEvent, ScrapedFighter

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, database_url: str):
        """Initialize with a synchronous database URL (postgresql://...)."""
        self.engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self.engine)

    def get_known_event_hashes(self) -> set[str]:
        """Return all event hashes already in the database."""
        with Session(self.engine) as session:
            result = session.execute(select(Event.ufcstats_hash))
            return {row[0] for row in result}

    def store_fighters(self, fighters: list[ScrapedFighter]):
        """Upsert fighters into the database."""
        with Session(self.engine) as session:
            for f in fighters:
                existing = session.execute(
                    select(Fighter).where(Fighter.ufcstats_hash == f.ufcstats_hash)
                ).scalar_one_or_none()

                if existing:
                    existing.name = f.name
                    existing.nickname = f.nickname
                    existing.height_inches = f.height_inches
                    existing.reach_inches = f.reach_inches
                    existing.dob = f.dob
                    existing.stance = f.stance
                else:
                    session.add(Fighter(
                        name=f.name,
                        nickname=f.nickname,
                        ufcstats_hash=f.ufcstats_hash,
                        height_inches=f.height_inches,
                        reach_inches=f.reach_inches,
                        dob=f.dob,
                        stance=f.stance,
                    ))
            session.commit()

    def store_event(self, event: ScrapedEvent):
        """Store an event and all its fights and round stats.

        If a BFO-created event (ufcstats_hash starting with 'bfo-') already
        exists with a matching name, it is upgraded in place so that odds
        records linked to its fights are preserved.
        """
        with Session(self.engine) as session:
            # Check if event already exists by ufcstats_hash
            existing_event = session.execute(
                select(Event).where(Event.ufcstats_hash == event.ufcstats_hash)
            ).scalar_one_or_none()

            if existing_event:
                logger.info(f"Event {event.name} already exists, skipping")
                return

            # Check for a BFO-created event with the same name to merge into
            bfo_event = session.execute(
                select(Event).where(
                    Event.ufcstats_hash.like("bfo-%"),
                    Event.name == event.name,
                )
            ).scalar_one_or_none()

            if bfo_event:
                # Upgrade the BFO event with real UFCStats data
                bfo_event.ufcstats_hash = event.ufcstats_hash
                bfo_event.date = event.date
                bfo_event.location = event.location
                db_event = bfo_event
                logger.info(f"Merging UFCStats data into existing BFO event: {event.name}")
            else:
                # Create new event
                db_event = Event(
                    name=event.name,
                    date=event.date,
                    location=event.location,
                    ufcstats_hash=event.ufcstats_hash,
                )
                session.add(db_event)
                session.flush()

            # Create fights
            for fight in event.fights:
                # Look up fighter IDs
                f1 = session.execute(
                    select(Fighter).where(Fighter.ufcstats_hash == fight.fighter_1_hash)
                ).scalar_one_or_none()
                f2 = session.execute(
                    select(Fighter).where(Fighter.ufcstats_hash == fight.fighter_2_hash)
                ).scalar_one_or_none()

                if not f1 or not f2:
                    logger.warning(
                        f"Skipping fight {fight.fighter_1_name} vs {fight.fighter_2_name}: "
                        f"fighter not found in DB"
                    )
                    continue

                # Check if this fight already exists (from BFO) — match by fighters + event
                existing_fight = session.execute(
                    select(Fight).where(
                        Fight.event_id == db_event.id,
                        (
                            ((Fight.fighter_1_id == f1.id) & (Fight.fighter_2_id == f2.id))
                            | ((Fight.fighter_1_id == f2.id) & (Fight.fighter_2_id == f1.id))
                        ),
                    )
                ).scalar_one_or_none()

                # Determine winner ID
                winner_id = None
                if fight.winner_name == fight.fighter_1_name:
                    winner_id = f1.id
                elif fight.winner_name == fight.fighter_2_name:
                    winner_id = f2.id

                if existing_fight:
                    # Update the BFO-created fight with results
                    existing_fight.winner_id = winner_id
                    existing_fight.weight_class = fight.weight_class
                    existing_fight.is_title_bout = fight.is_title_bout
                    existing_fight.method = fight.method
                    existing_fight.method_category = fight.method_category
                    existing_fight.finish_round = fight.finish_round
                    existing_fight.finish_time = fight.finish_time
                    existing_fight.total_rounds = fight.total_rounds
                    existing_fight.referee = fight.referee
                    existing_fight.result = fight.result
                    existing_fight.bout_order = fight.bout_order
                    db_fight = existing_fight
                    logger.info(f"Updated existing fight: {fight.fighter_1_name} vs {fight.fighter_2_name}")
                else:
                    db_fight = Fight(
                        event_id=db_event.id,
                        fighter_1_id=f1.id,
                        fighter_2_id=f2.id,
                        winner_id=winner_id,
                        weight_class=fight.weight_class,
                        is_title_bout=fight.is_title_bout,
                        method=fight.method,
                        method_category=fight.method_category,
                        finish_round=fight.finish_round,
                        finish_time=fight.finish_time,
                        total_rounds=fight.total_rounds,
                        referee=fight.referee,
                        result=fight.result,
                        bout_order=fight.bout_order,
                    )
                    session.add(db_fight)
                    session.flush()

                # Create round stats
                for rs in fight.round_stats:
                    # Look up the fighter for this round stat
                    rs_fighter = session.execute(
                        select(Fighter).where(Fighter.ufcstats_hash == rs.fighter_hash)
                    ).scalar_one_or_none()

                    if not rs_fighter:
                        continue

                    db_rs = RoundStats(
                        fight_id=db_fight.id,
                        fighter_id=rs_fighter.id,
                        round_number=rs.round_number,
                        knockdowns=rs.knockdowns,
                        sig_strikes_landed=rs.sig_strikes_landed,
                        sig_strikes_attempted=rs.sig_strikes_attempted,
                        total_strikes_landed=rs.total_strikes_landed,
                        total_strikes_attempted=rs.total_strikes_attempted,
                        takedowns_landed=rs.takedowns_landed,
                        takedowns_attempted=rs.takedowns_attempted,
                        submissions_attempted=rs.submissions_attempted,
                        reversals=rs.reversals,
                        control_time_seconds=rs.control_time_seconds,
                        head_strikes_landed=rs.head_strikes_landed,
                        head_strikes_attempted=rs.head_strikes_attempted,
                        body_strikes_landed=rs.body_strikes_landed,
                        body_strikes_attempted=rs.body_strikes_attempted,
                        leg_strikes_landed=rs.leg_strikes_landed,
                        leg_strikes_attempted=rs.leg_strikes_attempted,
                        distance_strikes_landed=rs.distance_strikes_landed,
                        distance_strikes_attempted=rs.distance_strikes_attempted,
                        clinch_strikes_landed=rs.clinch_strikes_landed,
                        clinch_strikes_attempted=rs.clinch_strikes_attempted,
                        ground_strikes_landed=rs.ground_strikes_landed,
                        ground_strikes_attempted=rs.ground_strikes_attempted,
                    )
                    session.add(db_rs)

            session.commit()
            logger.info(f"Stored event: {event.name} ({len(event.fights)} fights)")
