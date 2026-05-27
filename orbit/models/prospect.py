from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from orbit.database import Base


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    linkedin_url: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    context: Mapped[str] = mapped_column(Text, default="")
    relationship_state: Mapped[str] = mapped_column(String, default="cold")
    signal_score: Mapped[float] = mapped_column(Float, default=0.0)
    signal_density: Mapped[float] = mapped_column(Float, default=0.0)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_now: Mapped[str | None] = mapped_column(Text, nullable=True)
    shared_interests: Mapped[str | None] = mapped_column(Text, nullable=True)
    past_topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
