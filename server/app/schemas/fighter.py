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
