"""Phase 5 — Maps v2 + Evidence v2 tests.

Tests: heatmap data points, timeline data, video scan gate, evidence pairs.
"""

from __future__ import annotations

import pytest

from tk_api.media.scan import (
    ALLOWED_MIME,
    VIDEO_MIMES,
    ScanResult,
    scan_bytes,
)


# ---------------------------------------------------------------------------
# 1. Heatmap & Timeline schemas
# ---------------------------------------------------------------------------


def test_heatmap_point_schema():
    from tk_api.gis.schemas import HeatmapPoint

    p = HeatmapPoint(lon=75.7873, lat=26.9124, weight=2.0, severity="high", category="roads")
    assert p.lon == 75.7873
    assert p.weight == 2.0


def test_timeline_response_schema():
    from tk_api.gis.schemas import TimelinePeriod, TimelineResponse

    resp = TimelineResponse(
        interval="month",
        periods=[TimelinePeriod(period="2026-01", total=10, open=5, resolved=5)],
        total_reports=10,
    )
    assert resp.total_reports == 10
    assert len(resp.periods) == 1


# ---------------------------------------------------------------------------
# 2. Video MIME types in scan gate
# ---------------------------------------------------------------------------


def test_video_mimes_in_allowed():
    """Video MIME types are registered in the scan gate."""
    for mime in ("video/mp4", "video/quicktime", "video/webm"):
        assert mime in VIDEO_MIMES
        assert mime in ALLOWED_MIME


def test_scan_video_mp4_magic():
    """A valid MP4 magic bytes pass the scan gate."""
    # Minimal MP4 ftyp box header
    data = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 40
    result = scan_bytes(data, "video/mp4", 50 * 1024 * 1024)
    assert result.clean is True
    assert result.scan_status == "clean"


def test_scan_video_oversized():
    """Oversized video is rejected."""
    data = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100
    result = scan_bytes(data, "video/mp4", 10)  # 10 bytes limit
    assert result.clean is False
    assert result.scan_status == "error"


def test_scan_video_bad_magic():
    """Video with wrong magic bytes fails."""
    data = b"\x00\x00\x00\x00BAD_DATA_HERE" + b"\x00" * 40
    result = scan_bytes(data, "video/mp4", 50 * 1024 * 1024)
    assert result.clean is False
    assert result.scan_status == "infected"


def test_scan_webm_magic():
    """WebM magic bytes pass the scan gate."""
    data = b"\x1a\x45\xdf\xa3" + b"\x00" * 40
    result = scan_bytes(data, "video/webm", 50 * 1024 * 1024)
    assert result.clean is True


# ---------------------------------------------------------------------------
# 3. Evidence pair schemas
# ---------------------------------------------------------------------------


def test_report_media_pair_fields():
    """ReportMedia model has evidence v2 pair fields."""
    from tk_api.media.models import ReportMedia

    # Verify the columns exist in the model
    columns = {c.name for c in ReportMedia.__table__.columns}
    assert "pair_group" in columns
    assert "pair_role" in columns
    assert "captured_at" in columns


def test_media_object_video_fields():
    """MediaObject model has video evidence fields."""
    from tk_api.media.models import MediaObject

    columns = {c.name for c in MediaObject.__table__.columns}
    assert "duration_seconds" in columns
    assert "fps" in columns
    assert "codec" in columns


def test_evidence_chain_model():
    """EvidenceChain model exists with expected columns."""
    from tk_api.media.models import EvidenceChain

    columns = {c.name for c in EvidenceChain.__table__.columns}
    assert "id" in columns
    assert "report_id" in columns
    assert "chain_hash" in columns
    assert "evidence_count" in columns


# ---------------------------------------------------------------------------
# 4. Existing image scan still works
# ---------------------------------------------------------------------------


def test_scan_jpeg_still_works():
    """JPEG magic bytes still pass after video additions."""
    # Use real minimal JPEG for decodability check
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="JPEG")
    data = buf.getvalue()
    result = scan_bytes(data, "image/jpeg", 10 * 1024 * 1024)
    assert result.clean is True


def test_scan_png_still_works():
    """PNG magic bytes still pass."""
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buf, format="PNG")
    data = buf.getvalue()
    result = scan_bytes(data, "image/png", 10 * 1024 * 1024)
    assert result.clean is True


# ---------------------------------------------------------------------------
# 5. API endpoint registration
# ---------------------------------------------------------------------------


def test_gis_router_has_heatmap_endpoint():
    """The GIS router includes the new heatmap endpoint."""
    from tk_api.api.routers.gis import gis_router

    paths = {r.path for r in gis_router.routes}
    assert any("heatmap" in p for p in paths)


def test_gis_router_has_timeline_endpoint():
    """The GIS router includes the new timeline endpoint."""
    from tk_api.api.routers.gis import gis_router

    paths = {r.path for r in gis_router.routes}
    assert any("timeline" in p for p in paths)
