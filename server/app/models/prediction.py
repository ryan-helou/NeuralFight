from datetime import datetime

from sqlalchemy import Float, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(50))
    fighter_1_win_prob: Mapped[float] = mapped_column(Float)
    fighter_2_win_prob: Mapped[float] = mapped_column(Float)
    ko_tko_prob: Mapped[float | None] = mapped_column(Float)
    submission_prob: Mapped[float | None] = mapped_column(Float)
    decision_prob: Mapped[float | None] = mapped_column(Float)
    predicted_round: Mapped[int | None] = mapped_column(SmallInteger)
    round_probabilities: Mapped[dict | None] = mapped_column(JSONB)
    method_by_fighter: Mapped[dict | None] = mapped_column(JSONB)
    upset_score: Mapped[float | None] = mapped_column(Float)
    betting_confidence: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text)
    feature_importances: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
