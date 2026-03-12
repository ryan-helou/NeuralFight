from pydantic import BaseModel


class OddsOut(BaseModel):
    fight_id: int
    source: str
    fighter_1_name: str
    fighter_2_name: str
    fighter_1_decimal: float
    fighter_2_decimal: float
    fighter_1_american: int
    fighter_2_american: int
    fighter_1_implied: float
    fighter_2_implied: float
    retrieved_at: str

    model_config = {"from_attributes": True}
