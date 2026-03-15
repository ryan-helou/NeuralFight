from pydantic import BaseModel


class PredictionOut(BaseModel):
    fight_id: int
    model_version: str
    fighter_1_win_prob: float
    fighter_2_win_prob: float
    ko_tko_prob: float | None
    submission_prob: float | None
    decision_prob: float | None
    predicted_round: int | None
    round_probabilities: dict | None
    method_by_fighter: dict | None
    upset_score: float | None
    betting_confidence: float | None
    rationale: str | None
    feature_importances: list | None

    model_config = {"from_attributes": True}


class UpsetOut(BaseModel):
    fight_id: int
    fighter_1_name: str
    fighter_2_name: str
    event_name: str
    fighter_1_win_prob: float
    fighter_2_win_prob: float
    upset_score: float
    betting_confidence: float | None

    model_config = {"from_attributes": True}


class ValueBetOut(BaseModel):
    fight_id: int
    fighter_1_name: str
    fighter_2_name: str
    event_name: str
    event_date: str
    fighter_1_win_prob: float
    fighter_2_win_prob: float
    bet_on: str
    edge: float
    bet_amount: float
    american_odds: int
    decimal_odds: float
    vegas_implied: float
    ai_prob: float

    model_config = {"from_attributes": True}


class BetHistoryOut(BaseModel):
    fight_id: int
    fighter_1_name: str
    fighter_2_name: str
    event_name: str
    event_date: str
    weight_class: str | None
    bet_on: str
    edge: float
    bet_amount: float
    american_odds: int
    decimal_odds: float
    vegas_implied: float
    ai_prob: float
    winner_name: str | None
    won: bool | None
    payout: float | None

    model_config = {"from_attributes": True}
