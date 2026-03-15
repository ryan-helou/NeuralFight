from datetime import date

from pydantic import BaseModel


class FighterOut(BaseModel):
    id: int
    name: str
    nickname: str | None
    height_inches: int | None
    reach_inches: int | None
    dob: date | None
    stance: str | None

    model_config = {"from_attributes": True}


class FighterFightOut(BaseModel):
    fight_id: int
    event_name: str
    event_date: str
    opponent_name: str
    result: str | None  # "W", "L", "D", or None for upcoming
    method: str | None
    weight_class: str | None
    is_title_bout: bool


class FighterProfileOut(BaseModel):
    id: int
    name: str
    nickname: str | None
    height_inches: int | None
    reach_inches: int | None
    dob: str | None  # ISO date string
    stance: str | None
    wins: int
    losses: int
    draws: int
    ko_wins: int
    sub_wins: int
    dec_wins: int
    avg_sig_strikes: float
    avg_takedowns: float
    avg_knockdowns: float
    avg_control_time: float
    avg_sub_attempts: float
    recent_fights: list[FighterFightOut]
    upcoming_fights: list[FighterFightOut]
