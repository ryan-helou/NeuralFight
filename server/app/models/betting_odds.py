from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BettingOdds(Base):
    __tablename__ = "betting_odds"

    id: Mapped[int] = mapped_column(primary_key=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"), index=True)
    source: Mapped[str] = mapped_column(String(50))
    fighter_1_decimal: Mapped[float] = mapped_column(Float)
    fighter_2_decimal: Mapped[float] = mapped_column(Float)
    fighter_1_american: Mapped[int] = mapped_column(Integer)
    fighter_2_american: Mapped[int] = mapped_column(Integer)
    retrieved_at: Mapped[datetime] = mapped_column(server_default=func.now())
