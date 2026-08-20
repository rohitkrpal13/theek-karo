"""Government Data Connectors, SSRF Protection, and Normalization Adapters."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any

from tk_api.govdata.schemas import (
    CourtResourceModel,
    HospitalResourceModel,
    PoliceResourceModel,
    RoadResourceModel,
    SchoolResourceModel,
)


class ConnectorSecurityError(Exception):
    """Raised when a connector request violates SSRF or security boundaries."""


# -----------------------------------------------------------------------------
# 1. Security & Sanitization Utilities
# -----------------------------------------------------------------------------

# SSRF blocklist — the literals are denied hosts, not bind addresses.
_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"}  # nosec B104


def validate_source_url(url: str, allowlist_domains: set[str] | None = None) -> str:
    """Validate a remote URL against SSRF, private IP spaces, and disallowed schemes."""
    if not url or not isinstance(url, str):
        raise ConnectorSecurityError("URL must be a non-empty string.")

    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ConnectorSecurityError(
            f"Unsupported URL scheme: '{parsed.scheme}'. Only http/https allowed."
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ConnectorSecurityError("Invalid URL: missing hostname.")

    if hostname in _BLOCKED_HOSTNAMES:
        raise ConnectorSecurityError(f"Access to loopback/metadata host '{hostname}' is forbidden.")

    # Check for private IP address ranges
    try:
        ip = ipaddress.ip_address(hostname)
        is_ip = True
    except ValueError:
        is_ip = False

    if is_ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise ConnectorSecurityError(f"Access to private IP space '{hostname}' is forbidden.")

    if allowlist_domains and not any(
        hostname == d or hostname.endswith(f".{d}") for d in allowlist_domains
    ):
        raise ConnectorSecurityError(f"Host '{hostname}' is not in approved domain allowlist.")

    return url

    return url


def sanitize_csv_cell(value: Any) -> Any:
    """Sanitize CSV values against formula injection (=, +, -, @, tab, newline)."""
    if isinstance(value, str):
        val = value.strip()
        if val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{val}"
    return value


def scrub_pii(text: str) -> str:
    """Scrub potential 12-digit Aadhaar-like numbers or sensitive PII."""
    if not text or not isinstance(text, str):
        return text
    # Mask 12-digit Indian national ID / Aadhaar patterns
    scrubbed = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[REDACTED_ID]", text)
    return scrubbed


def compute_sha256(content: Any) -> str:
    """Compute deterministic SHA-256 checksum of payload."""
    if isinstance(content, str):
        raw = content.encode("utf-8")
    elif isinstance(content, bytes):
        raw = content
    else:
        raw = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# -----------------------------------------------------------------------------
# 2. Base Connector Interface
# -----------------------------------------------------------------------------


class GovernmentDataConnector(ABC):
    """Abstract Base Class for public dataset and official portal connectors."""

    connector_name: str = "generic_gov_connector"
    institution_type_code: str = "general"

    def __init__(self, allowed_domains: set[str] | None = None) -> None:
        self.allowed_domains = allowed_domains or {
            "gov.in",
            "nic.in",
            "data.gov.in",
            "udiseplus.gov.in",
            "nhp.gov.in",
            "cctns.gov.in",
            "ecourts.gov.in",
            "pmgsy.nic.in",
        }

    @abstractmethod
    def validate_schema(self, raw_data: dict[str, Any] | list[Any]) -> bool:
        """Validate structural compliance and data types of raw payload."""
        ...

    @abstractmethod
    def normalize_record(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        """Normalize an external record into a canonical model dictionary."""
        ...

    def extract_external_key(self, raw_record: dict[str, Any]) -> str:
        """Extract or synthesize a stable external key for entity resolution."""
        for key in (
            "udise_code",
            "school_code",
            "hospital_code",
            "facility_id",
            "station_code",
            "court_code",
            "project_code",
            "code",
            "id",
            "official_identifier",
        ):
            if raw_record.get(key):
                return str(raw_record[key]).strip()
        # Fallback to name hash — non-cryptographic entity-resolution key only
        name = str(raw_record.get("name", "unnamed")).strip()
        return hashlib.md5(name.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


# -----------------------------------------------------------------------------
# 3. Domain Connector Adapters
# -----------------------------------------------------------------------------


class UDISEPlusSchoolConnector(GovernmentDataConnector):
    """Connector for UDISE+ Educational Institutions."""

    connector_name = "udise_plus_school"
    institution_type_code = "school"

    def validate_schema(self, raw_data: dict[str, Any] | list[Any]) -> bool:
        records = raw_data if isinstance(raw_data, list) else raw_data.get("records", [raw_data])
        if not records:
            return False
        first = records[0]
        return "name" in first or "school_name" in first

    def normalize_record(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        code = str(raw_record.get("udise_code") or raw_record.get("school_code") or "").strip()
        name = str(
            raw_record.get("school_name") or raw_record.get("name") or "Government School"
        ).strip()

        model = SchoolResourceModel(
            school_code=code or None,
            management_type=raw_record.get("management", "govt"),
            category=raw_record.get("category", "secondary"),
            total_students=int(raw_record["total_students"])
            if "total_students" in raw_record
            else None,
            boys=int(raw_record["boys"]) if "boys" in raw_record else None,
            girls=int(raw_record["girls"]) if "girls" in raw_record else None,
            sanctioned_teachers=int(raw_record["sanctioned_teachers"])
            if "sanctioned_teachers" in raw_record
            else None,
            working_teachers=int(raw_record["working_teachers"])
            if "working_teachers" in raw_record
            else None,
            vacancies=int(raw_record["vacancies"]) if "vacancies" in raw_record else None,
            classrooms_total=int(raw_record["classrooms_total"])
            if "classrooms_total" in raw_record
            else None,
            usable_classrooms=int(raw_record["usable_classrooms"])
            if "usable_classrooms" in raw_record
            else None,
            toilets_total=int(raw_record["toilets_total"])
            if "toilets_total" in raw_record
            else None,
            girls_toilets=int(raw_record["girls_toilets"])
            if "girls_toilets" in raw_record
            else None,
            drinking_water_available=bool(raw_record.get("drinking_water", True)),
            electricity_available=bool(raw_record.get("electricity", True)),
            boundary_wall_status=str(raw_record.get("boundary_wall", "pucca")),
            library_available=bool(raw_record.get("library", False)),
            laboratory_available=bool(raw_record.get("laboratory", False)),
            playground_available=bool(raw_record.get("playground", True)),
            ramps_available=bool(raw_record.get("ramps", False)),
        )

        return {
            "name": name,
            "official_identifier": code or None,
            "type_code": "school",
            "canonical_data": model.model_dump(exclude_none=True),
        }


class NHPHospitalConnector(GovernmentDataConnector):
    """Connector for National Health Portal Hospital datasets."""

    connector_name = "nhp_hospital"
    institution_type_code = "hospital"

    def validate_schema(self, raw_data: dict[str, Any] | list[Any]) -> bool:
        records = raw_data if isinstance(raw_data, list) else raw_data.get("records", [raw_data])
        if not records:
            return False
        first = records[0]
        return "name" in first or "hospital_name" in first

    def normalize_record(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        code = str(raw_record.get("hospital_code") or raw_record.get("facility_id") or "").strip()
        name = str(
            raw_record.get("hospital_name") or raw_record.get("name") or "Government Hospital"
        ).strip()

        model = HospitalResourceModel(
            hospital_code=code or None,
            facility_type=raw_record.get("facility_type", "district_hospital"),
            total_beds=int(raw_record["total_beds"]) if "total_beds" in raw_record else None,
            icu_beds=int(raw_record["icu_beds"]) if "icu_beds" in raw_record else None,
            doctors_sanctioned=int(raw_record["doctors_sanctioned"])
            if "doctors_sanctioned" in raw_record
            else None,
            doctors_available=int(raw_record["doctors_available"])
            if "doctors_available" in raw_record
            else None,
            nurses_available=int(raw_record["nurses_available"])
            if "nurses_available" in raw_record
            else None,
            emergency_service_24x7=bool(raw_record.get("emergency_24x7", True)),
            pharmacy_available=bool(raw_record.get("pharmacy", True)),
            blood_bank_available=bool(raw_record.get("blood_bank", False)),
            diagnostic_labs=list(raw_record.get("labs", [])),
            ambulances_available=int(raw_record["ambulances"])
            if "ambulances" in raw_record
            else None,
            operating_status=raw_record.get("operating_status", "operational"),
        )

        return {
            "name": name,
            "official_identifier": code or None,
            "type_code": "hospital",
            "canonical_data": model.model_dump(exclude_none=True),
        }


class CCTNSPoliceConnector(GovernmentDataConnector):
    """Connector for CCTNS Police Stations."""

    connector_name = "cctns_police"
    institution_type_code = "police_station"

    def validate_schema(self, raw_data: dict[str, Any] | list[Any]) -> bool:
        records = raw_data if isinstance(raw_data, list) else raw_data.get("records", [raw_data])
        if not records:
            return False
        first = records[0]
        return "station_name" in first or "name" in first

    def normalize_record(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        code = str(raw_record.get("station_code") or "").strip()
        name = str(
            raw_record.get("station_name") or raw_record.get("name") or "Police Station"
        ).strip()

        model = PoliceResourceModel(
            station_code=code or None,
            jurisdiction_area=raw_record.get("jurisdiction"),
            circle_office=raw_record.get("circle"),
            helpline_phone=raw_record.get("helpline"),
            citizen_helpdesk_available=bool(raw_record.get("helpdesk", True)),
            women_helpdesk_available=bool(raw_record.get("women_helpdesk", True)),
            published_citizen_services=list(
                raw_record.get("services", ["FIR Registration", "Lost Article Report"])
            ),
        )

        return {
            "name": name,
            "official_identifier": code or None,
            "type_code": "police_station",
            "canonical_data": model.model_dump(exclude_none=True),
        }


class eCourtsConnector(GovernmentDataConnector):
    """Connector for eCourts District and Taluka Courts."""

    connector_name = "ecourts"
    institution_type_code = "court"

    def validate_schema(self, raw_data: dict[str, Any] | list[Any]) -> bool:
        records = raw_data if isinstance(raw_data, list) else raw_data.get("records", [raw_data])
        if not records:
            return False
        first = records[0]
        return "court_name" in first or "name" in first

    def normalize_record(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        code = str(raw_record.get("court_code") or "").strip()
        name = str(
            raw_record.get("court_name") or raw_record.get("name") or "District Court"
        ).strip()

        model = CourtResourceModel(
            court_code=code or None,
            court_type=raw_record.get("court_type", "district_court"),
            jurisdiction=raw_record.get("jurisdiction"),
            sanctioned_benches=int(raw_record["sanctioned_benches"])
            if "sanctioned_benches" in raw_record
            else None,
            digital_filing_available=bool(raw_record.get("digital_filing", True)),
            legal_aid_clinic_available=bool(raw_record.get("legal_aid", True)),
            e_seva_kendra_available=bool(raw_record.get("e_seva_kendra", True)),
        )

        return {
            "name": name,
            "official_identifier": code or None,
            "type_code": "court",
            "canonical_data": model.model_dump(exclude_none=True),
        }


class PMGSYRoadsConnector(GovernmentDataConnector):
    """Connector for PMGSY Public Works Road Infrastructure."""

    connector_name = "pmgsy_roads"
    institution_type_code = "road"

    def validate_schema(self, raw_data: dict[str, Any] | list[Any]) -> bool:
        records = raw_data if isinstance(raw_data, list) else raw_data.get("records", [raw_data])
        if not records:
            return False
        first = records[0]
        return "road_name" in first or "name" in first or "project_code" in first

    def normalize_record(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        code = str(raw_record.get("project_code") or raw_record.get("road_code") or "").strip()
        name = str(raw_record.get("road_name") or raw_record.get("name") or "Road Project").strip()

        model = RoadResourceModel(
            project_code=code or None,
            road_name=name,
            road_classification=raw_record.get("road_classification", "rural_road"),
            length_km=float(raw_record["length_km"]) if "length_km" in raw_record else None,
            executing_agency=raw_record.get("executing_agency", "PWD"),
            sanctioned_cost_lakhs=float(raw_record["sanctioned_cost_lakhs"])
            if "sanctioned_cost_lakhs" in raw_record
            else None,
            sanction_date=raw_record.get("sanction_date"),
            target_completion_date=raw_record.get("target_completion_date"),
            actual_completion_date=raw_record.get("actual_completion_date"),
            contractor_name=raw_record.get("contractor_name"),
            maintenance_status=raw_record.get("maintenance_status", "routine_maintenance"),
        )

        return {
            "name": name,
            "official_identifier": code or None,
            "type_code": "road",
            "canonical_data": model.model_dump(exclude_none=True),
        }


class GenericGovDataConnector(GovernmentDataConnector):
    """Generic connector for JSON/CSV key-value datasets."""

    connector_name = "generic_gov"
    institution_type_code = "general"

    def validate_schema(self, raw_data: dict[str, Any] | list[Any]) -> bool:
        records = raw_data if isinstance(raw_data, list) else raw_data.get("records", [raw_data])
        return len(records) > 0

    def normalize_record(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        name = str(
            raw_record.get("name") or raw_record.get("title") or "Public Institution"
        ).strip()
        identifier = str(
            raw_record.get("udise_code")
            or raw_record.get("code")
            or raw_record.get("identifier")
            or ""
        ).strip()
        return {
            "name": name,
            "official_identifier": identifier or None,
            "type_code": raw_record.get("type", "general"),
            "canonical_data": {k: v for k, v in raw_record.items() if not k.startswith("_")},
        }


# Connector Registry Mapping
CONNECTOR_REGISTRY: dict[str, type[GovernmentDataConnector]] = {
    "udise_plus_school": UDISEPlusSchoolConnector,
    "nhp_hospital": NHPHospitalConnector,
    "cctns_police": CCTNSPoliceConnector,
    "ecourts": eCourtsConnector,
    "pmgsy_roads": PMGSYRoadsConnector,
    "generic_gov": GenericGovDataConnector,
}


def get_connector(name: str) -> GovernmentDataConnector:
    """Retrieve connector instance by registered key."""
    cls = CONNECTOR_REGISTRY.get(name, GenericGovDataConnector)
    return cls()
