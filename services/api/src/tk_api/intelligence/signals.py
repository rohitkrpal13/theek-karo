"""Civic signal service (Phase 20, spec §6-§8, docs/INTELLIGENCE-METHODOLOGY.md).

Signals are stored summaries of what the deterministic engines noticed. Review
is append-only: :class:`IntelligenceReview` rows accumulate, the signal's
``status`` reflects the latest decision, and every review is mirrored to the
audit log (``Action: signals.review``). Creating a signal never modifies the
underlying reports/cases — signals are observations, not edits.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.geography.models import Geography
from tk_api.institutions.models import Institution
from tk_api.intelligence.models import (
    CivicSignal,
    IntelligenceReview,
    SignalEvidence,
    SignalSource,
)
from tk_api.intelligence.schemas import (
    ManualSignalCreate,
    ReviewActionRequest,
    SignalDetailResponse,
    SignalListResponse,
    SignalRead,
)
from tk_api.users.models import User


def _signal_to_read(
    s: CivicSignal,
    *,
    geo_names: dict[uuid.UUID, str] | None = None,
    inst_names: dict[uuid.UUID, str] | None = None,
    reviews: list[dict[str, Any]] | None = None,
) -> SignalRead:
    geos = geo_names or {}
    insts = inst_names or {}
    return SignalRead(
        id=s.id,
        signal_type=s.signal_type,
        title=s.title,
        description=s.description,
        category_slug=s.category_slug,
        geography_id=s.geography_id,
        geography_name=geos.get(s.geography_id) if s.geography_id else None,
        institution_id=s.institution_id,
        institution_name=insts.get(s.institution_id) if s.institution_id else None,
        severity=s.severity,
        confidence=s.confidence,
        status=s.status,
        visibility=s.visibility,
        evidence_count=s.evidence_count,
        source_count=s.source_count,
        observation_period=s.observation_period,
        payload=s.payload,
        explanation=s.explanation,
        detected_at=s.detected_at,
        created_at=s.created_at,
        review_history=reviews or [],
    )


async def _names(
    session: AsyncSession, signals: list[CivicSignal]
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    geo_names: dict[uuid.UUID, str] = {}
    inst_names: dict[uuid.UUID, str] = {}
    geo_ids = {s.geography_id for s in signals if s.geography_id}
    inst_ids = {s.institution_id for s in signals if s.institution_id}
    if geo_ids:
        for g in (
            await session.execute(select(Geography).where(Geography.id.in_(geo_ids)))
        ).scalars():
            geo_names[g.id] = g.name
    if inst_ids:
        for i in (
            await session.execute(select(Institution).where(Institution.id.in_(inst_ids)))
        ).scalars():
            inst_names[i.id] = i.name
    return geo_names, inst_names


_REVIEW_TO_STATUS = {
    "CONFIRM": "CONFIRMED_SIGNAL",
    "DISMISS": "DISMISSED",
    "REQUEST_MORE_DATA": "UNDER_REVIEW",
    "MONITOR": "MONITORING",
    "ESCALATE": "CONFIRMED_SIGNAL",
    "MARK_RESOLVED": "RESOLVED",
}


async def _reviews_for(session: AsyncSession, signal_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(IntelligenceReview)
            .where(IntelligenceReview.signal_id == signal_id)
            .order_by(IntelligenceReview.created_at.asc())
        )
    ).scalars()
    return [
        {"action": r.action, "note": r.note, "created_at": r.created_at.isoformat()} for r in rows
    ]


class SignalService:
    async def list(
        self,
        session: AsyncSession,
        *,
        signal_type: str | None = None,
        status: str | None = None,
        geography_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
        visibility: str | None = None,
        user: User | None = None,
    ) -> SignalListResponse:
        stmt = select(CivicSignal).order_by(CivicSignal.created_at.desc())
        if signal_type:
            stmt = stmt.where(CivicSignal.signal_type == signal_type)
        if status:
            stmt = stmt.where(CivicSignal.status == status)
        if geography_id:
            stmt = stmt.where(CivicSignal.geography_id == geography_id)
        if visibility:
            stmt = stmt.where(CivicSignal.visibility == visibility)
        elif user is None or not user.has_role("admin"):
            stmt = stmt.where(
                CivicSignal.visibility.in_(["PUBLIC", "COMMUNITY", "DEPARTMENT", "ADMIN"])
            )
        rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
        geo_names, inst_names = await _names(session, list(rows))
        count = len(rows)
        items = [_signal_to_read(s, geo_names=geo_names, inst_names=inst_names) for s in rows]
        return SignalListResponse(
            items=items,
            count=count,
            generated_at=datetime.now(UTC),
            note=(
                "A signal is a stored observation from the deterministic engines or a "
                "manual entry. Status reflects the latest human review decision."
            ),
        )

    async def get(self, session: AsyncSession, signal_id: uuid.UUID) -> SignalDetailResponse:
        signal = await session.get(CivicSignal, signal_id)
        if signal is None:
            raise ApiError("signal not found", 404, "signal_not_found")
        geo_names, inst_names = await _names(session, [signal])
        evidence_rows = (
            (
                await session.execute(
                    select(SignalEvidence)
                    .where(SignalEvidence.signal_id == signal_id)
                    .order_by(SignalEvidence.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        source_rows = (
            (
                await session.execute(
                    select(SignalSource)
                    .where(SignalSource.signal_id == signal_id)
                    .order_by(SignalSource.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        reviews = (
            (
                await session.execute(
                    select(IntelligenceReview)
                    .where(IntelligenceReview.signal_id == signal_id)
                    .order_by(IntelligenceReview.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        base = _signal_to_read(
            signal,
            geo_names=geo_names,
            inst_names=inst_names,
            reviews=[
                {"action": r.action, "note": r.note, "created_at": r.created_at.isoformat()}
                for r in reviews
            ],
        )
        detail = SignalDetailResponse(**base.model_dump())
        detail.evidence = [
            {
                "kind": e.kind,
                "entity_type": e.entity_type,
                "entity_id": str(e.entity_id) if e.entity_id else None,
                "payload": e.payload,
                "source": e.source,
                "created_at": e.created_at.isoformat(),
            }
            for e in evidence_rows
        ]
        detail.sources = [
            {
                "source_kind": s.source_kind,
                "source_name": s.source_name,
                "source_id": str(s.source_id) if s.source_id else None,
                "dataset_version": s.dataset_version,
                "retrieved_at": s.retrieved_at.isoformat() if s.retrieved_at else None,
                "note": s.note,
            }
            for s in source_rows
        ]
        detail.limitations = [
            "Signals use the deterministic Phase 20 engines; they are review triggers, "
            "never verdicts.",
            "Evidence and sources are captured at detection time and stored append-only.",
        ]
        return detail

    async def create_manual(
        self,
        session: AsyncSession,
        user: User,
        payload: ManualSignalCreate,
    ) -> SignalRead:
        signal = CivicSignal(
            signal_type=payload.signal_type,
            title=payload.title,
            description=payload.description,
            category_slug=payload.category_slug,
            geography_id=payload.geography_id,
            institution_id=payload.institution_id,
            severity=payload.severity,
            confidence=payload.confidence,
            status="NEW",
            visibility=payload.visibility,
            evidence_count=0,
            source_count=0,
            explanation={"source": "manual_entry", "reviewed_by": str(user.id)},
        )
        session.add(signal)
        await session.flush()
        await audit(
            session,
            action="signals.create",
            entity_type="civic_signals",
            entity_id=signal.id,
            actor_id=user.id,
            after={"title": signal.title, "signal_type": signal.signal_type},
        )
        return _signal_to_read(signal)

    async def review(
        self,
        session: AsyncSession,
        user: User,
        signal_id: uuid.UUID,
        payload: ReviewActionRequest,
    ) -> SignalRead:
        signal = await session.get(CivicSignal, signal_id)
        if signal is None:
            raise ApiError("signal not found", 404, "signal_not_found")
        session.add(
            IntelligenceReview(
                signal_id=signal.id,
                reviewer_id=user.id,
                action=payload.action,
                note=payload.note,
            )
        )
        signal.status = _REVIEW_TO_STATUS[payload.action]

        evidence = SignalEvidence(
            signal_id=signal.id,
            kind="review",
            entity_type="users",
            entity_id=user.id,
            payload={"action": payload.action, "note": payload.note},
            source="intelligence_review",
        )
        session.add(evidence)
        await session.flush()
        await audit(
            session,
            action="signals.review",
            entity_type="civic_signals",
            entity_id=signal.id,
            actor_id=user.id,
            after={"action": payload.action, "status": signal.status, "note": payload.note},
        )
        geo_names, inst_names = await _names(session, [signal])
        reviews = await _reviews_for(session, signal.id)
        return _signal_to_read(signal, geo_names=geo_names, inst_names=inst_names, reviews=reviews)
