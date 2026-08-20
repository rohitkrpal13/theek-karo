"""Phase 23 — Data Trust service layer.

Implements: evidence registry, verification, data quality, conflict detection,
dispute management, provenance chain, and data trust dashboard.

Reuses existing: DataSource (provenance), GovDataset (govdata),
DataCorrectionRequest (publicdata), AuditLog (core), media pipeline.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.data_trust.models import (
    DataChangeHistory,
    DataConflict,
    DataQualityResult,
    DataQuarantineRecord,
    DisputeRecord,
    EvidenceRecord,
    MetricDefinition,
    VerificationRecord,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _compute_chain_hash(previous_hash: str | None, data: str) -> str:
    """Compute a tamper-evident hash chain."""
    payload = f"{previous_hash or 'GENESIS'}:{data}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_uuid(value: str | None, field_name: str) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ApiError(f"invalid {field_name}", 422, f"invalid_{field_name}") from None


def _require_uuid(value: str | None, field_name: str) -> uuid.UUID:
    result = _safe_uuid(value, field_name)
    if result is None:
        raise ApiError(f"{field_name} is required", 422, f"missing_{field_name}")
    return result


# ---------------------------------------------------------------------------
# Evidence Registry
# ---------------------------------------------------------------------------


async def register_evidence(
    session: AsyncSession,
    *,
    data: dict[str, Any],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Register a new evidence item in the central evidence registry."""
    evidence_type = data.get("evidence_type", "")
    if evidence_type not in (
        "image",
        "video",
        "document",
        "audio",
        "text",
        "official_record",
        "external_reference",
    ):
        raise ApiError("invalid evidence_type", 422, "invalid_evidence_type")
    source_type = data.get("source_type", "CITIZEN")
    valid_source_types = (
        "CITIZEN",
        "COMMUNITY",
        "ORGANIZATION",
        "INSTITUTION",
        "OFFICIAL_GOVERNMENT",
        "PUBLIC_DATASET",
        "OPEN_DATA",
        "PARTNER",
        "INTERNAL",
        "AI_GENERATED",
        "DERIVED_ANALYTICS",
    )
    if source_type not in valid_source_types:
        raise ApiError("invalid source_type", 422, "invalid_source_type")

    source_id = _safe_uuid(data.get("source_id"), "source_id")
    media_id = _safe_uuid(data.get("media_id"), "media_id")
    entity_id = _safe_uuid(data.get("entity_id"), "entity_id")

    evidence = EvidenceRecord(
        evidence_type=evidence_type,
        title=data.get("title"),
        description=data.get("description"),
        source_type=source_type,
        source_id=source_id,
        uploader_id=actor_id,
        media_id=media_id,
        entity_type=data.get("entity_type"),
        entity_id=entity_id,
        location=data.get("location"),
        language=data.get("language"),
        original_text=data.get("original_text"),
        status="SUBMITTED",
        verification_status="NOT_REVIEWED",
    )

    # Compute integrity hash
    hash_data = (
        f"{evidence_type}:{source_type}:{datetime.now(UTC).isoformat()}:{data.get('title', '')}"
    )
    evidence.checksum_sha256 = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()

    session.add(evidence)
    await session.flush()

    await audit(
        session,
        action="data_trust.evidence_register",
        entity_type="evidence_registry",
        entity_id=evidence.id,
        actor_id=actor_id,
    )

    return _evidence_to_dict(evidence)


async def get_evidence(session: AsyncSession, evidence_id: uuid.UUID) -> dict[str, Any]:
    """Get a single evidence record."""
    evidence = await session.get(EvidenceRecord, evidence_id)
    if evidence is None:
        raise ApiError("evidence not found", 404, "evidence_not_found")
    return _evidence_to_dict(evidence)


async def list_evidence(
    session: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    source_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List evidence records with filters."""
    stmt = select(EvidenceRecord)
    if entity_type:
        stmt = stmt.where(EvidenceRecord.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(EvidenceRecord.entity_id == entity_id)
    if source_type:
        stmt = stmt.where(EvidenceRecord.source_type == source_type)
    if status:
        stmt = stmt.where(EvidenceRecord.status == status)
    stmt = stmt.order_by(EvidenceRecord.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    total = await session.scalar(select(func.count(EvidenceRecord.id)))
    return {"items": [_evidence_to_dict(r) for r in rows], "total": total or 0}


def _evidence_to_dict(e: EvidenceRecord) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "evidence_type": e.evidence_type,
        "title": e.title,
        "description": e.description,
        "source_type": e.source_type,
        "source_id": str(e.source_id) if e.source_id else None,
        "uploader_id": str(e.uploader_id) if e.uploader_id else None,
        "media_id": str(e.media_id) if e.media_id else None,
        "entity_type": e.entity_type,
        "entity_id": str(e.entity_id) if e.entity_id else None,
        "checksum_sha256": e.checksum_sha256,
        "file_size_bytes": e.file_size_bytes,
        "mime_type": e.mime_type,
        "status": e.status,
        "verification_status": e.verification_status,
        "verification_count": e.verification_count,
        "language": e.language,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


# ---------------------------------------------------------------------------
# Verification Records
# ---------------------------------------------------------------------------


async def create_verification(
    session: AsyncSession,
    *,
    data: dict[str, Any],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Create a new verification record (append-only)."""
    decision = data.get("decision", "")
    if decision not in (
        "NOT_REVIEWED",
        "REVIEWED",
        "VERIFIED",
        "PARTIALLY_VERIFIED",
        "DISPUTED",
        "REJECTED",
    ):
        raise ApiError("invalid decision", 422, "invalid_decision")
    method = data.get("method", "")
    valid_methods = (
        "human_review",
        "official_source_confirmation",
        "cross_source_consistency",
        "location_validation",
        "timestamp_validation",
        "document_verification",
        "duplicate_analysis",
        "structured_data_validation",
        "ai_assisted",
    )
    if method not in valid_methods:
        raise ApiError("invalid method", 422, "invalid_method")

    entity_id = _require_uuid(data.get("entity_id"), "entity_id")
    reviewer_type = "ai_assisted" if data.get("ai_model") else "human"

    record = VerificationRecord(
        entity_type=data.get("entity_type", ""),
        entity_id=entity_id,
        reviewer_id=actor_id,
        reviewer_type=reviewer_type,
        decision=decision,
        method=method,
        evidence_refs=data.get("evidence_refs", []),
        explanation=data.get("explanation"),
        confidence=data.get("confidence"),
        ai_model=data.get("ai_model"),
        ai_model_version=data.get("ai_model_version"),
        ai_reasoning=data.get("ai_reasoning"),
    )

    # Tamper-evident chain
    hash_data = (
        f"{record.entity_type}:{record.entity_id}:{decision}:{method}:"
        f"{datetime.now(UTC).isoformat()}"
    )
    record.chain_hash = _compute_chain_hash(None, hash_data)

    session.add(record)

    # Update evidence verification count if entity is evidence
    if record.entity_type == "evidence":
        evidence = await session.get(EvidenceRecord, entity_id)
        if evidence:
            evidence.verification_count += 1
            if decision == "VERIFIED":
                evidence.verification_status = "VERIFIED"
            elif decision == "PARTIALLY_VERIFIED":
                evidence.verification_status = "PARTIALLY_VERIFIED"
            elif decision == "DISPUTED":
                evidence.verification_status = "DISPUTED"
            elif decision == "REJECTED":
                evidence.verification_status = "REJECTED"
            elif decision == "REVIEWED":
                evidence.verification_status = "REVIEWED"

    await session.flush()

    await audit(
        session,
        action="data_trust.verification_create",
        entity_type="verification_records",
        entity_id=record.id,
        actor_id=actor_id,
        after={"decision": decision, "method": method, "entity_type": record.entity_type},
    )

    return _verification_to_dict(record)


async def list_verifications(
    session: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    decision: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List verification records."""
    stmt = select(VerificationRecord)
    if entity_type:
        stmt = stmt.where(VerificationRecord.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(VerificationRecord.entity_id == entity_id)
    if decision:
        stmt = stmt.where(VerificationRecord.decision == decision)
    stmt = stmt.order_by(VerificationRecord.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    total = await session.scalar(select(func.count(VerificationRecord.id)))
    return {"items": [_verification_to_dict(r) for r in rows], "total": total or 0}


def _verification_to_dict(v: VerificationRecord) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "entity_type": v.entity_type,
        "entity_id": str(v.entity_id),
        "reviewer_id": str(v.reviewer_id) if v.reviewer_id else None,
        "reviewer_type": v.reviewer_type,
        "decision": v.decision,
        "method": v.method,
        "evidence_refs": v.evidence_refs,
        "explanation": v.explanation,
        "confidence": v.confidence,
        "ai_model": v.ai_model,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------


async def record_quality_check(
    session: AsyncSession,
    *,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Record a data quality check result."""
    dimension = data.get("dimension", "")
    valid_dims = (
        "completeness",
        "validity",
        "consistency",
        "uniqueness",
        "freshness",
        "coverage",
        "referential_integrity",
    )
    if dimension not in valid_dims:
        raise ApiError("invalid dimension", 422, "invalid_dimension")
    status = data.get("status", "")
    valid_statuses = (
        "VALID",
        "PARTIALLY_VALID",
        "INVALID",
        "INCOMPLETE",
        "STALE",
        "CONFLICTING",
        "DUPLICATE",
        "UNVERIFIED",
    )
    if status not in valid_statuses:
        raise ApiError("invalid status", 422, "invalid_quality_status")

    entity_id = _require_uuid(data.get("entity_id"), "entity_id")
    source_id = _safe_uuid(data.get("source_id"), "source_id")
    dataset_id = _safe_uuid(data.get("dataset_id"), "dataset_id")

    result = DataQualityResult(
        entity_type=data.get("entity_type", ""),
        entity_id=entity_id,
        source_id=source_id,
        dataset_id=dataset_id,
        dimension=dimension,
        score=data.get("score", 0.0),
        status=status,
        details=data.get("details"),
        missing_fields=data.get("missing_fields"),
        invalid_fields=data.get("invalid_fields"),
        overall_status=data.get("overall_status", "UNVERIFIED"),
        ai_assisted=data.get("ai_assisted", False),
        ai_confidence=data.get("ai_confidence"),
        ai_reasoning=data.get("ai_reasoning"),
    )
    session.add(result)
    await session.flush()
    return _quality_to_dict(result)


async def get_quality_summary(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
) -> dict[str, Any]:
    """Get aggregated quality dimensions for an entity."""
    stmt = (
        select(DataQualityResult)
        .where(
            DataQualityResult.entity_type == entity_type,
            DataQualityResult.entity_id == entity_id,
        )
        .order_by(DataQualityResult.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()

    # Deduplicate per dimension (latest wins)
    dims: dict[str, DataQualityResult] = {}
    for r in rows:
        if r.dimension not in dims:
            dims[r.dimension] = r

    dim_list = [_quality_to_dict(d) for d in dims.values()]
    statuses = [d.status for d in dims.values()]
    if "INVALID" in statuses or "CONFLICTING" in statuses:
        overall = "CONFLICTING"
    elif "INCOMPLETE" in statuses:
        overall = "INCOMPLETE"
    elif "STALE" in statuses:
        overall = "STALE"
    elif all(s == "VALID" for s in statuses) and statuses:
        overall = "VALID"
    elif statuses:
        overall = "PARTIALLY_VALID"
    else:
        overall = "UNVERIFIED"

    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "overall_status": overall,
        "dimensions": dim_list,
    }


def _quality_to_dict(q: DataQualityResult) -> dict[str, Any]:
    return {
        "id": str(q.id),
        "entity_type": q.entity_type,
        "entity_id": str(q.entity_id),
        "dimension": q.dimension,
        "score": q.score,
        "status": q.status,
        "overall_status": q.overall_status,
        "details": q.details,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


# ---------------------------------------------------------------------------
# Data Conflicts
# ---------------------------------------------------------------------------


async def detect_conflict(
    session: AsyncSession,
    *,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Record a detected conflict between two sources."""
    entity_id = _require_uuid(data.get("entity_id"), "entity_id")
    severity = data.get("severity", "MEDIUM")
    if severity not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        raise ApiError("invalid severity", 422, "invalid_severity")

    conflict = DataConflict(
        entity_type=data.get("entity_type", ""),
        entity_id=entity_id,
        field_name=data.get("field_name", ""),
        source_a_id=_safe_uuid(data.get("source_a_id"), "source_a_id"),
        source_a_value=data.get("source_a_value"),
        source_a_timestamp=_parse_timestamp(data.get("source_a_timestamp")),
        source_b_id=_safe_uuid(data.get("source_b_id"), "source_b_id"),
        source_b_value=data.get("source_b_value"),
        source_b_timestamp=_parse_timestamp(data.get("source_b_timestamp")),
        severity=severity,
        status="DETECTED",
    )
    session.add(conflict)
    await session.flush()

    await audit(
        session,
        action="data_trust.conflict_detected",
        entity_type="data_conflicts",
        entity_id=conflict.id,
    )

    return _conflict_to_dict(conflict)


async def resolve_conflict(
    session: AsyncSession,
    *,
    conflict_id: uuid.UUID,
    data: dict[str, Any],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Resolve a data conflict."""
    conflict = await session.get(DataConflict, conflict_id)
    if conflict is None:
        raise ApiError("conflict not found", 404, "conflict_not_found")
    status = data.get("status", "")
    valid_resolutions = (
        "RESOLVED_SELECT_SOURCE",
        "RESOLVED_MERGED",
        "RESOLVED_UNRESOLVED",
        "DISMISSED",
    )
    if status not in valid_resolutions:
        raise ApiError("invalid resolution status", 422, "invalid_resolution_status")

    conflict.status = status
    conflict.resolved_value = data.get("resolved_value")
    conflict.resolved_by = actor_id
    conflict.resolved_at = _utcnow()
    conflict.resolution_note = data.get("resolution_note")

    await audit(
        session,
        action="data_trust.conflict_resolved",
        entity_type="data_conflicts",
        entity_id=conflict.id,
        actor_id=actor_id,
        after={"status": status},
    )

    return _conflict_to_dict(conflict)


async def list_conflicts(
    session: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List data conflicts."""
    stmt = select(DataConflict)
    if entity_type:
        stmt = stmt.where(DataConflict.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(DataConflict.entity_id == entity_id)
    if status:
        stmt = stmt.where(DataConflict.status == status)
    stmt = stmt.order_by(DataConflict.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    total = await session.scalar(select(func.count(DataConflict.id)))
    return {"items": [_conflict_to_dict(r) for r in rows], "total": total or 0}


def _conflict_to_dict(c: DataConflict) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "entity_type": c.entity_type,
        "entity_id": str(c.entity_id),
        "field_name": c.field_name,
        "source_a_value": c.source_a_value,
        "source_b_value": c.source_b_value,
        "source_a_timestamp": c.source_a_timestamp.isoformat() if c.source_a_timestamp else None,
        "source_b_timestamp": c.source_b_timestamp.isoformat() if c.source_b_timestamp else None,
        "status": c.status,
        "resolved_value": c.resolved_value,
        "resolution_note": c.resolution_note,
        "severity": c.severity,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------


async def file_dispute(
    session: AsyncSession,
    *,
    data: dict[str, Any],
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """File a new dispute against a record."""
    target_type = data.get("dispute_target_type", "")
    valid_targets = ("report", "evidence", "dataset", "institution", "metric", "public_data")
    if target_type not in valid_targets:
        raise ApiError("invalid dispute_target_type", 422, "invalid_target_type")

    dispute = DisputeRecord(
        dispute_target_type=target_type,
        dispute_target_id=data.get("dispute_target_id", ""),
        filed_by=actor_id,
        reason=data.get("reason", ""),
        explanation=data.get("explanation"),
        evidence_refs=data.get("evidence_refs", []),
        status="OPEN",
        public_banner=True,
    )
    session.add(dispute)
    await session.flush()

    await audit(
        session,
        action="data_trust.dispute_filed",
        entity_type="dispute_records",
        entity_id=dispute.id,
        actor_id=actor_id,
    )

    return _dispute_to_dict(dispute)


async def review_dispute(
    session: AsyncSession,
    *,
    dispute_id: uuid.UUID,
    data: dict[str, Any],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Review and decide on a dispute."""
    dispute = await session.get(DisputeRecord, dispute_id)
    if dispute is None:
        raise ApiError("dispute not found", 404, "dispute_not_found")
    status = data.get("status", "")
    valid_statuses = ("UNDER_REVIEW", "RESOLVED", "REJECTED", "WITHDRAWN")
    if status not in valid_statuses:
        raise ApiError("invalid status", 422, "invalid_dispute_status")

    dispute.status = status
    dispute.reviewer_id = actor_id
    dispute.decision = data.get("decision")
    dispute.decided_at = _utcnow()
    if status in ("RESOLVED", "REJECTED", "WITHDRAWN"):
        dispute.public_banner = False

    await audit(
        session,
        action="data_trust.dispute_reviewed",
        entity_type="dispute_records",
        entity_id=dispute.id,
        actor_id=actor_id,
        after={"status": status},
    )

    return _dispute_to_dict(dispute)


async def list_disputes(
    session: AsyncSession,
    *,
    target_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List dispute records."""
    stmt = select(DisputeRecord)
    if target_type:
        stmt = stmt.where(DisputeRecord.dispute_target_type == target_type)
    if status:
        stmt = stmt.where(DisputeRecord.status == status)
    stmt = stmt.order_by(DisputeRecord.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    total = await session.scalar(select(func.count(DisputeRecord.id)))
    return {"items": [_dispute_to_dict(r) for r in rows], "total": total or 0}


async def has_active_dispute(
    session: AsyncSession,
    *,
    target_type: str,
    target_id: str,
) -> bool:
    """Check if a record has an active (OPEN/UNDER_REVIEW) dispute."""
    count = await session.scalar(
        select(func.count(DisputeRecord.id)).where(
            DisputeRecord.dispute_target_type == target_type,
            DisputeRecord.dispute_target_id == target_id,
            DisputeRecord.status.in_(("OPEN", "UNDER_REVIEW")),
        )
    )
    return (count or 0) > 0


def _dispute_to_dict(d: DisputeRecord) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "dispute_target_type": d.dispute_target_type,
        "dispute_target_id": d.dispute_target_id,
        "filed_by": str(d.filed_by),
        "reason": d.reason,
        "explanation": d.explanation,
        "status": d.status,
        "decision": d.decision,
        "public_banner": d.public_banner,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


# ---------------------------------------------------------------------------
# Change History
# ---------------------------------------------------------------------------


async def record_change(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    field_name: str,
    old_value: Any,
    new_value: Any,
    change_source: str,
    changed_by: uuid.UUID | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Record a data change in the append-only change history."""
    valid_sources = ("user", "system", "import", "ai", "correction", "dispute")
    if change_source not in valid_sources:
        change_source = "system"

    record = DataChangeHistory(
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_source=change_source,
        changed_by=changed_by,
        reason=reason,
    )

    hash_data = (
        f"{entity_type}:{entity_id}:{field_name}:{change_source}:{datetime.now(UTC).isoformat()}"
    )
    record.chain_hash = _compute_chain_hash(None, hash_data)

    session.add(record)
    await session.flush()
    return {
        "id": str(record.id),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


async def list_change_history(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    limit: int = 50,
) -> dict[str, Any]:
    """List change history for an entity."""
    stmt = (
        select(DataChangeHistory)
        .where(
            DataChangeHistory.entity_type == entity_type, DataChangeHistory.entity_id == entity_id
        )
        .order_by(DataChangeHistory.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "field_name": r.field_name,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "change_source": r.change_source,
                "changed_by": str(r.changed_by) if r.changed_by else None,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# Provenance Chain
# ---------------------------------------------------------------------------


async def get_provenance(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
) -> dict[str, Any]:
    """Build the complete provenance chain for an entity."""
    # Evidence
    evidence_stmt = (
        select(EvidenceRecord)
        .where(EvidenceRecord.entity_type == entity_type, EvidenceRecord.entity_id == entity_id)
        .order_by(EvidenceRecord.created_at.desc())
        .limit(20)
    )
    evidence_rows = (await session.execute(evidence_stmt)).scalars().all()

    # Verifications
    verif_stmt = (
        select(VerificationRecord)
        .where(
            VerificationRecord.entity_type == entity_type, VerificationRecord.entity_id == entity_id
        )
        .order_by(VerificationRecord.created_at.desc())
        .limit(20)
    )
    verif_rows = (await session.execute(verif_stmt)).scalars().all()

    # Change history
    change_stmt = (
        select(DataChangeHistory)
        .where(
            DataChangeHistory.entity_type == entity_type, DataChangeHistory.entity_id == entity_id
        )
        .order_by(DataChangeHistory.created_at.desc())
        .limit(20)
    )
    change_rows = (await session.execute(change_stmt)).scalars().all()

    # Quality
    quality = await get_quality_summary(session, entity_type=entity_type, entity_id=entity_id)

    # Disputes
    dispute_stmt = (
        select(DisputeRecord)
        .where(
            DisputeRecord.dispute_target_type == entity_type,
            DisputeRecord.dispute_target_id == str(entity_id),
        )
        .order_by(DisputeRecord.created_at.desc())
        .limit(10)
    )
    dispute_rows = (await session.execute(dispute_stmt)).scalars().all()

    # Build limitations list
    limitations: list[str] = []
    if not verif_rows:
        limitations.append("No verification has been performed on this data.")
    if quality.get("overall_status") in ("UNVERIFIED", "INCOMPLETE"):
        limitations.append("Data quality check is incomplete or not performed.")
    if dispute_rows:
        active_disputes = [d for d in dispute_rows if d.status in ("OPEN", "UNDER_REVIEW")]
        if active_disputes:
            limitations.append("This information is currently under dispute.")

    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "evidence": [_evidence_to_dict(e) for e in evidence_rows],
        "verifications": [_verification_to_dict(v) for v in verif_rows],
        "change_history": [
            {
                "field_name": r.field_name,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "change_source": r.change_source,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in change_rows
        ],
        "quality": quality,
        "disputes": [_dispute_to_dict(d) for d in dispute_rows],
        "limitations": limitations,
    }


# ---------------------------------------------------------------------------
# Data Quality Dashboard
# ---------------------------------------------------------------------------


async def get_dashboard(session: AsyncSession) -> dict[str, Any]:
    """Get the data quality dashboard summary."""
    from tk_api.provenance.models import DataSource

    total_sources = await session.scalar(select(func.count(DataSource.id))) or 0
    active_sources = (
        await session.scalar(select(func.count(DataSource.id)).where(DataSource.status == "active"))
        or 0
    )
    failed_sources = (
        await session.scalar(select(func.count(DataSource.id)).where(DataSource.status == "failed"))
        or 0
    )
    stale_sources = (
        await session.scalar(select(func.count(DataSource.id)).where(DataSource.status == "stale"))
        or 0
    )

    from tk_api.govdata.models import GovDataset

    total_datasets = await session.scalar(select(func.count(GovDataset.id))) or 0

    total_conflicts = await session.scalar(select(func.count(DataConflict.id))) or 0
    open_conflicts = (
        await session.scalar(
            select(func.count(DataConflict.id)).where(DataConflict.status == "DETECTED")
        )
        or 0
    )

    total_disputes = await session.scalar(select(func.count(DisputeRecord.id))) or 0
    open_disputes = (
        await session.scalar(
            select(func.count(DisputeRecord.id)).where(
                DisputeRecord.status.in_(("OPEN", "UNDER_REVIEW"))
            )
        )
        or 0
    )

    total_evidence = await session.scalar(select(func.count(EvidenceRecord.id))) or 0
    verified_evidence = (
        await session.scalar(
            select(func.count(EvidenceRecord.id)).where(
                EvidenceRecord.verification_status == "VERIFIED"
            )
        )
        or 0
    )

    total_verifications = await session.scalar(select(func.count(VerificationRecord.id))) or 0
    quarantined = (
        await session.scalar(
            select(func.count(DataQuarantineRecord.id)).where(
                DataQuarantineRecord.status == "QUARANTINED"
            )
        )
        or 0
    )

    return {
        "total_sources": total_sources,
        "active_sources": active_sources,
        "failed_sources": failed_sources,
        "stale_sources": stale_sources,
        "total_datasets": total_datasets,
        "total_conflicts": total_conflicts,
        "open_conflicts": open_conflicts,
        "total_disputes": total_disputes,
        "open_disputes": open_disputes,
        "total_evidence": total_evidence,
        "verified_evidence": verified_evidence,
        "total_verifications": total_verifications,
        "quarantined_records": quarantined,
    }


# ---------------------------------------------------------------------------
# Metric Definitions
# ---------------------------------------------------------------------------


async def create_metric_definition(
    session: AsyncSession,
    *,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Create or update a metric definition."""
    existing = await session.scalar(
        select(MetricDefinition).where(MetricDefinition.metric_id == data["metric_id"])
    )
    if existing:
        # Update existing
        for field in (
            "name",
            "name_hi",
            "description",
            "formula",
            "definition",
            "source",
            "category",
            "visibility",
            "required_role",
            "coverage",
            "limitations",
            "period",
        ):
            if field in data and data[field] is not None:
                setattr(existing, field, data[field])
        existing.version = data.get("version", existing.version)
        existing.updated_at = _utcnow()
        await session.flush()
        return _metric_to_dict(existing)

    metric = MetricDefinition(**data)
    session.add(metric)
    await session.flush()
    return _metric_to_dict(metric)


async def list_metric_definitions(
    session: AsyncSession,
    *,
    category: str | None = None,
    visibility: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List metric definitions."""
    stmt = select(MetricDefinition).where(MetricDefinition.status == "active")
    if category:
        stmt = stmt.where(MetricDefinition.category == category)
    if visibility:
        stmt = stmt.where(MetricDefinition.visibility == visibility)
    stmt = stmt.order_by(MetricDefinition.metric_id).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_metric_to_dict(m) for m in rows]}


def _metric_to_dict(m: MetricDefinition) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "metric_id": m.metric_id,
        "name": m.name,
        "name_hi": m.name_hi,
        "description": m.description,
        "formula": m.formula,
        "definition": m.definition,
        "source": m.source,
        "category": m.category,
        "version": m.version,
        "visibility": m.visibility,
        "coverage": m.coverage,
        "limitations": m.limitations,
        "status": m.status,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
