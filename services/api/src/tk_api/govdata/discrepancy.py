"""Rule-based Discrepancy Engine for comparing Official Benchmarks and Citizen Observations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from tk_api.govdata.schemas import DiscrepancyItemRead, DiscrepancyState
from tk_api.reports.models import Report


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _is_recent(dt: datetime | None, cutoff: datetime) -> bool:
    if dt is None:
        return False
    u = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return u >= cutoff


def detect_discrepancies(
    *,
    institution_id: uuid.UUID,
    canonical_data: dict[str, Any],
    reports: list[Report],
    publication_date: datetime | None = None,
) -> list[DiscrepancyItemRead]:
    """Evaluate discrepancy rules between official data and citizen reports."""
    discrepancies: list[DiscrepancyItemRead] = []
    now = _utcnow()
    recent_cutoff = now - timedelta(days=90)
    recent_reports = [r for r in reports if _is_recent(r.created_at, recent_cutoff)]

    pub_utc = _as_utc(publication_date)
    is_outdated = pub_utc is not None and (now - pub_utc).days > 365

    # -------------------------------------------------------------------------
    # Rule 1: Staffing (Teachers / Doctors) Discrepancy
    # -------------------------------------------------------------------------
    sanctioned = canonical_data.get("sanctioned_teachers") or canonical_data.get(
        "doctors_sanctioned"
    )
    working = canonical_data.get("working_teachers") or canonical_data.get("doctors_available")
    vacancies = canonical_data.get("vacancies")

    staff_reports = [
        r
        for r in recent_reports
        if any(
            w in r.title.lower() or w in r.description.lower()
            for w in ("teacher", "doctor", "staff", "vacancy", "shortage")
        )
    ]

    if sanctioned is not None or working is not None:
        state: DiscrepancyState = "NO_DISCREPANCY_DETECTED"
        note = "Official staffing records and citizen reports align within expected parameters."
        finding = None

        if len(staff_reports) >= 2:
            if is_outdated:
                state = "OUTDATED_OFFICIAL_DATA"
                note = (
                    f"{len(staff_reports)} recent citizen observations mention staffing concerns; "
                    "official dataset last published over 12 months ago."
                )
                finding = (
                    "Official staffing baseline may be outdated relative to current observations."
                )
            else:
                state = "POSSIBLE_DISCREPANCY"
                note = (
                    f"{len(staff_reports)} citizen reports mention staffing shortages, "
                    f"while official records show {working or sanctioned} staff."
                )
                finding = (
                    "Possible discrepancy between published staff figures and "
                    "recent community reports."
                )

        discrepancies.append(
            DiscrepancyItemRead(
                id=uuid.uuid4(),
                institution_id=institution_id,
                resource_key="staffing",
                discrepancy_state=state,
                official_value={
                    "sanctioned": sanctioned,
                    "working": working,
                    "vacancies": vacancies,
                },
                citizen_summary=f"{len(staff_reports)} citizen reports on staffing",
                ai_finding=finding or note,
                confidence=0.75 if len(staff_reports) >= 2 else 0.50,
                rule_code="DISC_STAFF_01",
                severity="medium" if state == "POSSIBLE_DISCREPANCY" else "low",
                status="active",
                created_at=now,
            )
        )

    # -------------------------------------------------------------------------
    # Rule 2: Sanitation & Toilets
    # -------------------------------------------------------------------------
    toilets_official = canonical_data.get("toilets_total") or canonical_data.get(
        "usable_classrooms"
    )
    toilet_reports = [
        r
        for r in recent_reports
        if any(
            w in r.title.lower() or w in r.description.lower()
            for w in ("toilet", "washroom", "sanitation", "latrine", "bathroom")
        )
    ]

    if toilets_official is not None or "toilets_total" in canonical_data:
        state = "NO_DISCREPANCY_DETECTED"
        note = "Official sanitation capacity matches current observations."
        finding = None

        if len(toilet_reports) >= 2:
            state = "POSSIBLE_DISCREPANCY"
            note = (
                f"{len(toilet_reports)} reports indicate unusable or broken toilets; "
                f"official record states {toilets_official} toilets available."
            )
            finding = (
                "Observation reports indicate maintenance breakdown in published toilet facilities."
            )

        discrepancies.append(
            DiscrepancyItemRead(
                id=uuid.uuid4(),
                institution_id=institution_id,
                resource_key="toilets",
                discrepancy_state=state,
                official_value={"count": toilets_official},
                citizen_summary=f"{len(toilet_reports)} reports on sanitation facilities",
                ai_finding=finding or note,
                confidence=0.80 if len(toilet_reports) >= 2 else 0.50,
                rule_code="DISC_TOILET_01",
                severity="high" if state == "POSSIBLE_DISCREPANCY" else "low",
                status="active",
                created_at=now,
            )
        )

    # -------------------------------------------------------------------------
    # Rule 3: Drinking Water Availability
    # -------------------------------------------------------------------------
    water_official = canonical_data.get("drinking_water_available")
    water_reports = [
        r
        for r in recent_reports
        if any(
            w in r.title.lower() or w in r.description.lower()
            for w in ("water", "drinking water", "tap", "pipeline", "filter", "ro")
        )
    ]

    if water_official is not None:
        state = "NO_DISCREPANCY_DETECTED"
        note = "Drinking water reported functional."
        finding = None

        if water_official is True and len(water_reports) >= 2:
            state = "POSSIBLE_DISCREPANCY"
            note = (
                f"{len(water_reports)} recent reports mention lack of drinking water, "
                "whereas official baseline records water as available."
            )
            finding = "Recent observations indicate drinking water interruption."

        discrepancies.append(
            DiscrepancyItemRead(
                id=uuid.uuid4(),
                institution_id=institution_id,
                resource_key="drinking_water",
                discrepancy_state=state,
                official_value={"available": water_official},
                citizen_summary=f"{len(water_reports)} reports on water supply",
                ai_finding=finding or note,
                confidence=0.85 if len(water_reports) >= 2 else 0.50,
                rule_code="DISC_WATER_01",
                severity="high" if state == "POSSIBLE_DISCREPANCY" else "low",
                status="active",
                created_at=now,
            )
        )

    # -------------------------------------------------------------------------
    # Rule 4: Electricity & Power Supply
    # -------------------------------------------------------------------------
    elec_official = canonical_data.get("electricity_available")
    elec_reports = [
        r
        for r in recent_reports
        if any(
            w in r.title.lower() or w in r.description.lower()
            for w in ("electricity", "power", "meter", "wiring", "blackout")
        )
    ]

    if elec_official is not None:
        state = "NO_DISCREPANCY_DETECTED"
        note = "Power supply status consistent."
        finding = None

        if elec_official is True and len(elec_reports) >= 2:
            state = "POSSIBLE_DISCREPANCY"
            note = (
                f"{len(elec_reports)} reports indicate power outage/wiring failure; "
                "official data indicates functional electricity."
            )
            finding = "Citizen reports indicate electrical infrastructure defects."

        discrepancies.append(
            DiscrepancyItemRead(
                id=uuid.uuid4(),
                institution_id=institution_id,
                resource_key="electricity",
                discrepancy_state=state,
                official_value={"available": elec_official},
                citizen_summary=f"{len(elec_reports)} reports on power supply",
                ai_finding=finding or note,
                confidence=0.75 if len(elec_reports) >= 2 else 0.50,
                rule_code="DISC_ELEC_01",
                severity="medium" if state == "POSSIBLE_DISCREPANCY" else "low",
                status="active",
                created_at=now,
            )
        )

    return discrepancies
