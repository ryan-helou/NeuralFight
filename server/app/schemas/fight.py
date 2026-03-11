from pydantic import BaseModel

from app.schemas.fighter import FighterOut


class RoundStatsOut(BaseModel):
    round_number: int
    knockdowns: int | None
    sig_strikes_landed: int | None
    sig_strikes_attempted: int | None
    total_strikes_landed: int | None
    total_strikes_attempted: int | None
    takedowns_landed: int | None
    takedowns_attempted: int | None
    submissions_attempted: int | None
    reversals: int | None
    control_time_seconds: int | None
    head_strikes_landed: int | None
    head_strikes_attempted: int | None
    body_strikes_landed: int | None
    body_strikes_attempted: int | None
    leg_strikes_landed: int | None
    leg_strikes_attempted: int | None
    distance_strikes_landed: int | None
    distance_strikes_attempted: int | None
    clinch_strikes_landed: int | None
    clinch_strikes_attempted: int | None
    ground_strikes_landed: int | None
    ground_strikes_attempted: int | None

    model_config = {"from_attributes": True}


class FightDetailOut(BaseModel):
    id: int
    event_name: str
    fighter_1: FighterOut
    fighter_2: FighterOut
    winner_name: str | None
    weight_class: str | None
    is_title_bout: bool
    method: str | None
    method_category: str | None
    finish_round: int | None
    finish_time: str | None
    total_rounds: int | None
    referee: str | None
    result: str | None
    fighter_1_rounds: list[RoundStatsOut] = []
    fighter_2_rounds: list[RoundStatsOut] = []

    model_config = {"from_attributes": True}
