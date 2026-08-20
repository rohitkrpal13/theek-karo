"""Media entities (DATABASE.md §3.4, API.md §7)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MediaObject(Base):
    __tablename__ = "media_objects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bucket: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    # Phase 5 — Evidence v2: video support
    duration_seconds: Mapped[float | None] = mapped_column(BigInteger)
    fps: Mapped[float | None] = mapped_column(Integer)
    codec: Mapped[str | None] = mapped_column(String(32))
    scan_status: Mapped[str] = mapped_column(String(16), default="pending")
    status: Mapped[str] = mapped_column(String(16), default="uploading")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReportMedia(Base):
    __tablename__ = "report_media"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True
    )
    media_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_objects.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # evidence | resolution | verification

    # Phase 5 — Evidence v2: before/after pair support
    pair_group: Mapped[str | None] = mapped_column(String(64))  # groups before/after
    pair_role: Mapped[str | None] = mapped_column(String(16))  # before | after | standalone
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvidenceChain(Base):
    """Phase 5 — Evidence v2: tamper-evident chain linking evidence items."""
    __tablename__ = "evidence_chains"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    chain_hash: Mapped[str] = mapped_column(Text)  # SHA-256 of ordered evidence hashes
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
