from datetime import date

from pydantic import BaseModel


class ScrapedFighter(BaseModel):
    name: str
    nickname: str | None = None
    ufcstats_hash: str
    height_inches: int | None = None
    reach_inches: int | None = None
    dob: date | None = None
    stance: str | None = None


class ScrapedRoundStats(BaseModel):
    fighter_name: str
    fighter_hash: str
    round_number: int
    knockdowns: int = 0
    sig_strikes_landed: int = 0
    sig_strikes_attempted: int = 0
    total_strikes_landed: int = 0
    total_strikes_attempted: int = 0
    takedowns_landed: int = 0
    takedowns_attempted: int = 0
    submissions_attempted: int = 0
    reversals: int = 0
    control_time_seconds: int = 0
    head_strikes_landed: int = 0
    head_strikes_attempted: int = 0
    body_strikes_landed: int = 0
    body_strikes_attempted: int = 0
    leg_strikes_landed: int = 0
    leg_strikes_attempted: int = 0
    distance_strikes_landed: int = 0
    distance_strikes_attempted: int = 0
    clinch_strikes_landed: int = 0
    clinch_strikes_attempted: int = 0
    ground_strikes_landed: int = 0
    ground_strikes_attempted: int = 0


class ScrapedFight(BaseModel):
    ufcstats_hash: str
    fighter_1_name: str
    fighter_1_hash: str
    fighter_2_name: str
    fighter_2_hash: str
    winner_name: str | None = None
    weight_class: str | None = None
    is_title_bout: bool = False
    method: str | None = None
    method_category: str | None = None
    finish_round: int | None = None
    finish_time: str | None = None
    total_rounds: int | None = None
    referee: str | None = None
    result: str | None = None
    bout_order: int | None = None
    round_stats: list[ScrapedRoundStats] = []


class ScrapedEvent(BaseModel):
    name: str
    date: date
    location: str | None = None
    ufcstats_hash: str
    fights: list[ScrapedFight] = []
