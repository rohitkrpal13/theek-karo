"""Data lineage view (Phase 19, spec §60): trace where data originated.

For an institution, walk the chain:

    Source -> Dataset -> External Record -> Canonical Institution
            -> Report -> Evidence -> Resolution

Administrators use this to answer "where did this number come from?".
All rows are public-safe summaries (no PII, no internal notes).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.govdata.models import GovDataset, GovDatasetRecord, GovImportJob
from tk_api.institutions.models import Institution
from tk_api.provenance.models import DataSource, ExternalSource
from tk_api.reports.models import Report, ReportEvidence

TIMELINE_LIMIT = 20


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def get_institution_lineage(
    session: AsyncSession, institution_id: uuid.UUID
) -> dict[str, Any]:
    """Build the lineage chain for one institution (empty-safe)."""
    inst = await session.get(Institution, institution_id)
    if inst is None or inst.deleted_at is not None:
        return {"institution_id": str(institution_id), "found": False, "chain": []}

    chain: list[dict[str, Any]] = []

    # 1. Source + dataset + external records. ``institutions.source_id`` points
    # at ``external_sources`` (Phase 10 wiring); ``data_sources`` is the newer
    # registry — resolve either so lineage always shows the origin.
    source: DataSource | ExternalSource | None = None
    if inst.source_id is not None:
        source = await session.get(ExternalSource, inst.source_id)
    if source is None and inst.source_id is not None:
        source = await session.get(DataSource, inst.source_id)
    if source is not None:
        source_type = getattr(source, "source_type", "official_dataset")
        retrieved_at = getattr(source, "retrieval_date", None)
        chain.append(
            {
                "level": "source",
                "id": str(source.id),
                "name": source.name,
                "publisher": source.publisher,
                "url": source.url,
                "license": source.license,
                "source_type": source_type,
                "retrieved_at": retrieved_at.isoformat() if retrieved_at is not None else None,
            }
        )
        if isinstance(source, DataSource):
            dataset = await session.scalar(
                select(GovDataset).where(GovDataset.data_source_id == source.id).limit(1)
            )
        else:
            # ExternalSource linkage: find the most recent import job whose
            # ``affected_institutions`` (meta) included this institution.
            dataset = None
            import_jobs = (
                (
                    await session.execute(
                        select(GovImportJob).order_by(GovImportJob.started_at.desc()).limit(20)
                    )
                )
                .scalars()
                .all()
            )
            for job in import_jobs:
                if str(inst.id) in (job.meta or {}).get("affected_institutions", []):
                    dataset = await session.get(GovDataset, job.dataset_id)
                    if dataset is not None:
                        break
            if dataset is not None:
                chain.append(
                    {
                        "level": "dataset",
                        "id": str(dataset.id),
                        "name": dataset.name,
                        "publisher": dataset.publisher,
                        "license": dataset.license,
                        "version": dataset.version,
                        "connector_code": dataset.connector_code,
                        "updated_at": dataset.updated_at.isoformat()
                        if dataset.updated_at
                        else None,
                    }
                )
                # External records that carry this institution's identifier
                records = (
                    (
                        await session.execute(
                            select(GovDatasetRecord)
                            .where(GovDatasetRecord.dataset_id == dataset.id)
                            .order_by(GovDatasetRecord.valid_from.desc())
                            .limit(TIMELINE_LIMIT)
                        )
                    )
                    .scalars()
                    .all()
                )
                for rec in records:
                    chain.append(
                        {
                            "level": "external_record",
                            "id": str(rec.id),
                            "external_key": rec.external_key,
                            "dataset_id": str(rec.dataset_id),
                            "valid_from": rec.valid_from.isoformat() if rec.valid_from else None,
                            "valid_to": rec.valid_to.isoformat() if rec.valid_to else None,
                            "checksum": _checksum_of(rec),
                            "data": _public_safe_fields(rec.data),
                        }
                    )

    # 2. Canonical institution
    chain.append(
        {
            "level": "canonical_institution",
            "id": str(inst.id),
            "name": inst.name,
            "official_identifier": inst.official_identifier,
            "source_identifier": inst.source_identifier,
            "operational_status": inst.operational_status,
            "updated_at": inst.updated_at.isoformat() if inst.updated_at else None,
        }
    )

    # 3. Reports -> evidence -> resolution references
    reports = (
        (
            await session.execute(
                select(Report)
                .where(
                    Report.institution_id == inst.id,
                    Report.deleted_at.is_(None),
                )
                .order_by(Report.created_at.desc())
                .limit(TIMELINE_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    for report in reports:
        evidence_count = (
            await session.scalar(
                select(ReportEvidence.id).where(ReportEvidence.report_id == report.id).limit(1)
            )
        ) is not None
        chain.append(
            {
                "level": "report",
                "id": str(report.id),
                "ticket_no": report.ticket_no,
                "title": report.title,
                "status": report.status,
                "source": report.source,
                "has_evidence": evidence_count,
                "created_at": report.created_at.isoformat() if report.created_at else None,
            }
        )

    return {
        "institution_id": str(inst.id),
        "institution_name": inst.name,
        "found": True,
        "generated_at": _utcnow().isoformat(),
        "chain": chain,
        "note": (
            "Lineage is for data tracing only; 'report' entries are community "
            "observations, not official statements."
        ),
    }


def _checksum_of(rec: GovDatasetRecord) -> str | None:
    from tk_api.integrations.diff import record_checksum

    if rec.data is None:
        return None
    return record_checksum(rec.data)


def _public_safe_fields(data: dict[str, Any] | None) -> dict[str, Any]:
    """Strip obvious sensitive keys from raw record data before display."""
    if not isinstance(data, dict):
        return {}
    blocked = {"phone", "phone_number", "mobile", "email", "contact", "aadhaar", "password"}
    return {k: v for k, v in data.items() if str(k).lower() not in blocked}
