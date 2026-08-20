"""Content translation entities (PRD §22): never overwrite original content."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ContentTranslation(Base):
    __tablename__ = "content_translations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    content_type: Mapped[str] = mapped_column(String(32))
    content_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    locale: Mapped[str] = mapped_column(String(8))
    original_language: Mapped[str] = mapped_column(String(8))
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    translation_source: Mapped[str] = mapped_column(String(16))
    model_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
