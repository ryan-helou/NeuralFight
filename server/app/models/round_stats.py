from sqlalchemy import ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RoundStats(Base):
    __tablename__ = "round_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"), index=True)
    fighter_id: Mapped[int] = mapped_column(ForeignKey("fighters.id"))
    round_number: Mapped[int] = mapped_column(SmallInteger)
    knockdowns: Mapped[int | None] = mapped_column(SmallInteger)
    sig_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    sig_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    total_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    total_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    takedowns_landed: Mapped[int | None] = mapped_column(SmallInteger)
    takedowns_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    submissions_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    reversals: Mapped[int | None] = mapped_column(SmallInteger)
    control_time_seconds: Mapped[int | None] = mapped_column(Integer)
    head_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    head_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    body_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    body_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    leg_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    leg_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    distance_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    distance_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    clinch_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    clinch_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    ground_strikes_landed: Mapped[int | None] = mapped_column(SmallInteger)
    ground_strikes_attempted: Mapped[int | None] = mapped_column(SmallInteger)

    fight = relationship("Fight", back_populates="rounds")
    fighter = relationship("Fighter")
