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
