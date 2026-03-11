from datetime import date, datetime

from sqlalchemy import Date, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Fighter(Base):
    __tablename__ = "fighters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    nickname: Mapped[str | None] = mapped_column(String(200))
    ufcstats_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    height_inches: Mapped[int | None] = mapped_column(SmallInteger)
    reach_inches: Mapped[int | None] = mapped_column(SmallInteger)
    dob: Mapped[date | None] = mapped_column(Date)
    stance: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
