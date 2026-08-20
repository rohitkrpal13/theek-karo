"""Schemas for Government Data, Canonical Resource Models, and Discrepancies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# -----------------------------------------------------------------------------
# 1. Canonical Resource Models (Domain-specific structured attributes)
# -----------------------------------------------------------------------------


class SchoolResourceModel(BaseModel):
    """Canonical model for educational institutions (e.g. UDISE+)."""

    model_config = ConfigDict(extra="ignore")

    school_code: str | None = None
    management_type: str | None = None  # govt, govt_aided, private, municipal
    category: str | None = None  # primary, upper_primary, secondary, higher_secondary
    total_students: int | None = None
    boys: int | None = None
    girls: int | None = None
    sanctioned_teachers: int | None = None
    working_teachers: int | None = None
    vacancies: int | None = None
    classrooms_total: int | None = None
    usable_classrooms: int | None = None
    toilets_total: int | None = None
    girls_toilets: int | None = None
    drinking_water_available: bool | None = None
    electricity_available: bool | None = None
    boundary_wall_status: str | None = None
    library_available: bool | None = None
    laboratory_available: bool | None = None
    playground_available: bool | None = None
    ramps_available: bool | None = None
    accessible_toilets: bool | None = None


class HospitalResourceModel(BaseModel):
    """Canonical model for healthcare institutions (e.g. NHP)."""

    model_config = ConfigDict(extra="ignore")

    hospital_code: str | None = None
    facility_type: str | None = None  # phc, chc, district_hospital, medical_college
    total_beds: int | None = None
    icu_beds: int | None = None
    doctors_sanctioned: int | None = None
    doctors_available: int | None = None
    nurses_available: int | None = None
    emergency_service_24x7: bool | None = None
    pharmacy_available: bool | None = None
    blood_bank_available: bool | None = None
    diagnostic_labs: list[str] = Field(default_factory=list)
    ambulances_available: int | None = None
    operating_status: str | None = "operational"


class PoliceResourceModel(BaseModel):
    """Canonical model for police stations and law enforcement posts (e.g. CCTNS)."""

    model_config = ConfigDict(extra="ignore")

    station_code: str | None = None
    jurisdiction_area: str | None = None
    circle_office: str | None = None
    helpline_phone: str | None = None
    citizen_helpdesk_available: bool | None = None
    women_helpdesk_available: bool | None = None
    lockup_facility_available: bool | None = None
    published_citizen_services: list[str] = Field(default_factory=list)


class CourtResourceModel(BaseModel):
    """Canonical model for judicial institutions and district courts (eCourts)."""

    model_config = ConfigDict(extra="ignore")

    court_code: str | None = None
    court_type: str | None = None  # high_court, district_court, taluka_court, consumer_forum
    jurisdiction: str | None = None
    sanctioned_benches: int | None = None
    digital_filing_available: bool | None = None
    legal_aid_clinic_available: bool | None = None
    e_seva_kendra_available: bool | None = None


class RoadResourceModel(BaseModel):
    """Canonical model for public works and road infrastructure (PMGSY)."""

    model_config = ConfigDict(extra="ignore")

    project_code: str | None = None
    road_name: str | None = None
    road_classification: str | None = None  # national_highway, state_highway, mdr, rural_road
    length_km: float | None = None
    executing_agency: str | None = None
    sanctioned_cost_lakhs: float | None = None
    sanction_date: str | None = None
    target_completion_date: str | None = None
    actual_completion_date: str | None = None
    contractor_name: str | None = None
    maintenance_status: str | None = None


# -----------------------------------------------------------------------------
# 2. Provenance & Source Schemas
# -----------------------------------------------------------------------------


class DataSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source_type: str
    publisher: str | None = None
    url: str | None = None
    license: str | None = None
    dataset_identifier: str | None = None
    version: str | None = None
    confidence_base: float
    verification_state: str
    publication_date: datetime | None = None
    retrieval_date: datetime
    created_at: datetime
    # Phase 19 registry completeness (spec §10, §13): authority level, terms,
    # docs URL, expected update frequency, last verified, status.
    authority_level: str | None = None
    documentation_url: str | None = None
    terms: str | None = None
    update_frequency_hours: int | None = None
    last_verified_at: datetime | None = None
    status: str = "active"


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    source_type: str
    publisher: str | None = None
    url: str | None = None
    license: str | None = None
    dataset_identifier: str | None = None
    version: str | None = None
    confidence_base: float = 0.8
    verification_state: str = "official"


class ProvenanceDetailRead(BaseModel):
    source_id: uuid.UUID
    source_name: str
    publisher: str
    dataset_identifier: str | None = None
    dataset_version: str | None = None
    license: str | None = None
    source_url: str | None = None
    retrieval_date: datetime
    publication_date: datetime | None = None
    checksum_sha256: str | None = None
    transformation_version: str = "canonical_v1"


# -----------------------------------------------------------------------------
# 3. Discrepancy & Comparison Schemas
# -----------------------------------------------------------------------------

DiscrepancyState = Literal[
    "NO_DISCREPANCY_DETECTED",
    "POSSIBLE_DISCREPANCY",
    "CONFLICTING_DATA",
    "OUTDATED_OFFICIAL_DATA",
    "INSUFFICIENT_DATA",
    "UNDER_REVIEW",
    "RESOLVED",
]


class DiscrepancyItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    resource_key: str
    discrepancy_state: DiscrepancyState
    official_value: Any | None = None
    citizen_summary: str | None = None
    ai_finding: str | None = None
    confidence: float = 0.5
    rule_code: str | None = None
    severity: str = "medium"
    status: str = "active"
    reviewed_at: datetime | None = None
    created_at: datetime


class OfficialDataRead(BaseModel):
    institution_id: uuid.UUID
    institution_name: str
    institution_type: str
    official_identifier: str | None = None
    operational_status: str
    canonical_data: dict[str, Any]
    provenance: ProvenanceDetailRead | None = None
    last_published: datetime | None = None
    last_retrieved: datetime | None = None
    freshness_label: str


class ResourceComparisonItem(BaseModel):
    resource_key: str
    label: str
    official_value: Any | None = None
    official_source: str | None = None
    official_updated_at: str | None = None
    citizen_reports_count: int = 0
    citizen_observation_summary: str | None = None
    discrepancy_state: DiscrepancyState
    ai_analysis_note: str | None = None


class InstitutionComparisonRead(BaseModel):
    institution_id: uuid.UUID
    institution_name: str
    institution_type: str
    official_data_coverage_pct: float
    citizen_report_count: int
    overall_discrepancy_state: DiscrepancyState
    comparison_matrix: list[ResourceComparisonItem]
    provenance: ProvenanceDetailRead | None = None
    last_reconciled_at: datetime


# -----------------------------------------------------------------------------
# 4. Ingestion, Staging & Quality Schemas
# -----------------------------------------------------------------------------


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    run_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    rows_total: int | None = 0
    rows_imported: int | None = 0
    error: str | None = None
    # Phase 19 change-detection counters + drift flag (spec §15, §72)
    rows_added: int | None = None
    rows_removed: int | None = None
    rows_modified: int | None = None
    rows_unchanged: int | None = None
    rows_rejected: int | None = None
    schema_drift_flagged: bool = False
    preview_only: bool = False


class ImportJobCreate(BaseModel):
    dataset_id: uuid.UUID
    dry_run: bool = False
    raw_payload: dict[str, Any] | None = None
    # Phase 19: run large imports in the background worker (spec §32) instead
    # of inside the HTTP request; ``force`` overrides schema-drift protection
    # (spec §72); ``preview_only`` returns the change-detection preview without
    # writing anything (spec §70).
    background: bool = False
    force: bool = False
    preview_only: bool = False


class EntityMatchReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    external_key: str
    raw_data: dict[str, Any]
    candidate_institution_id: uuid.UUID | None = None
    candidate_institution_name: str | None = None
    match_confidence: float
    match_status: str
    match_signals: dict[str, Any] | None = None
    review_status: str
    created_at: datetime


class EntityMatchReviewDecision(BaseModel):
    decision: Literal["confirm", "reject", "reassign", "create_new"]
    target_institution_id: uuid.UUID | None = None
    notes: str | None = None


class DataQualityReportRead(BaseModel):
    total_datasets: int
    healthy_datasets: int
    stale_datasets: int
    failed_datasets: int
    total_institutions: int
    institutions_with_official_data: int
    official_data_coverage_pct: float
    pending_entity_matches_count: int
    total_discrepancies_flagged: int
