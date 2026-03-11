from sqlalchemy import Boolean, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Fight(Base):
    __tablename__ = "fights"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    fighter_1_id: Mapped[int] = mapped_column(ForeignKey("fighters.id"))
    fighter_2_id: Mapped[int] = mapped_column(ForeignKey("fighters.id"))
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("fighters.id"))
    weight_class: Mapped[str | None] = mapped_column(String(50))
    is_title_bout: Mapped[bool] = mapped_column(Boolean, default=False)
    method: Mapped[str | None] = mapped_column(String(100))
    method_category: Mapped[str | None] = mapped_column(String(20))
    finish_round: Mapped[int | None] = mapped_column(SmallInteger)
    finish_time: Mapped[str | None] = mapped_column(String(10))
    total_rounds: Mapped[int | None] = mapped_column(SmallInteger)
    referee: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[str | None] = mapped_column(String(20))
    bout_order: Mapped[int | None] = mapped_column(SmallInteger)

    event = relationship("Event", lazy="selectin")
    fighter_1 = relationship("Fighter", foreign_keys=[fighter_1_id], lazy="selectin")
    fighter_2 = relationship("Fighter", foreign_keys=[fighter_2_id], lazy="selectin")
    winner = relationship("Fighter", foreign_keys=[winner_id], lazy="selectin")
    rounds = relationship("RoundStats", back_populates="fight", lazy="selectin")
