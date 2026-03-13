from datetime import date

from pydantic import BaseModel


class EventOut(BaseModel):
    id: int
    name: str
    date: date
    location: str | None
    fight_count: int = 0

    model_config = {"from_attributes": True}


class EventDetailOut(BaseModel):
    id: int
    name: str
    date: date
    location: str | None
    fights: list["FightSummaryOut"] = []

    model_config = {"from_attributes": True}


class FightSummaryOut(BaseModel):
    id: int
    fighter_1_name: str
    fighter_2_name: str
    weight_class: str | None
    is_title_bout: bool
    method: str | None
    result: str | None
    winner_name: str | None
    fighter_1_win_prob: float | None = None
    fighter_2_win_prob: float | None = None
    vegas_fighter_1_implied: float | None = None
    vegas_fighter_2_implied: float | None = None
    fighter_1_american: int | None = None
    fighter_2_american: int | None = None
    upset_score: float | None = None
    bet_amount: float | None = None
    bet_on: str | None = None
    bet_decimal_odds: float | None = None

    model_config = {"from_attributes": True}
