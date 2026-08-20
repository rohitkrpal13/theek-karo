"""Media scan gate and thumbnails (API.md §7, SECURITY.md §6).

Dev implementation of the ClamAV slot: magic-byte verification, decodability
check, dimension extraction, and thumbnail generation via Pillow. Phase 8 moves
scanning into the worker and can swap ``scan_bytes`` for a real ClamAV adapter
behind the same signature. The gate itself never changes: media is only
``available`` when the scan reports ``clean``.

Hardening (Step 6): signatures are full-strength (WebP requires the RIFF+WEBP
fourccs, PNG the full 8-byte signature), and the payload must actually decode as
the declared image type (blocks HTML/polyglot spoofs). Pixel/dimension caps
neutralize decompression bombs — a tiny file declaring a 40000x40000 image is
rejected before any decoder work.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

# Decompression-bomb caps: reject images that would need absurd decode buffers.
MAX_IMAGE_PIXELS = 40_000_000  # 40 MP
MAX_IMAGE_DIMENSION = 12_000

_magic: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",
    # Phase 5 — Evidence v2: video support (magic bytes)
    "video/mp4": b"\x00\x00\x00\x18ftyp",
    "video/quicktime": b"\x00\x00\x00\x14ftyp",
    "video/webm": b"\x1a\x45\xdf\xa3",
}

# WebP files are RIFF containers; require the "WEBP" fourcc at offset 8 so WAV/
# AVI/other RIFF containers cannot masquerade as webp.
_webp_fourcc = b"WEBP"

# Phase 5 — Evidence v2: video-specific validation
VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/webm"}
MAX_VIDEO_SIZE_MB = 50
MAX_VIDEO_DURATION_S = 300  # 5 minutes

ALLOWED_MIME = tuple(_magic)


@dataclass
class ScanResult:
    clean: bool
    scan_status: str  # clean | infected | error
    detail: str = ""


def scan_bytes(data: bytes, mime: str, max_size_bytes: int) -> ScanResult:
    """Size + magic + decodability gate. ``infected``-grade results are treated
    as unacceptable by the media service (fails the scan-gate)."""
    if len(data) > max_size_bytes:
        return ScanResult(False, "error", "declared size exceeds limit")
    if len(data) < 12:
        return ScanResult(False, "infected", "content too short for declared MIME type")
    marker = _magic.get(mime)
    if marker is None or not data.startswith(marker):
        return ScanResult(False, "infected", "content does not match declared MIME type")
    if mime == "image/webp" and data[8:12] != _webp_fourcc:
        return ScanResult(False, "infected", "content does not match declared MIME type")

    # Phase 5 — Evidence v2: video validation (magic-byte only, no full decode)
    if mime in VIDEO_MIMES:
        if len(data) > MAX_VIDEO_SIZE_MB * 1024 * 1024:
            return ScanResult(False, "error", f"video exceeds {MAX_VIDEO_SIZE_MB}MB limit")
        # Basic magic-byte pass is sufficient for video; full scan in worker
        return ScanResult(True, "clean", "video magic bytes match declared MIME type")

    # Decodability + dimension caps: a payload must actually parse as the
    # declared image type, and must stay within safe pixel/dimension limits.
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if (
                width * height > MAX_IMAGE_PIXELS
                or width > MAX_IMAGE_DIMENSION
                or height > MAX_IMAGE_DIMENSION
            ):
                return ScanResult(False, "error", "image dimensions exceed the allowed limit")
            image.verify()
    except Exception:
        return ScanResult(False, "infected", "content does not match declared MIME type")
    return ScanResult(True, "clean", "magic bytes and image structure match declared MIME type")


def probe_image(data: bytes) -> tuple[int | None, int | None]:
    """Return (width, height) for an image loadable by Pillow, else (None, None)."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as image:
            return image.width, image.height
    except Exception:
        return None, None


def make_thumbnail(data: bytes, *, max_width: int = 640) -> bytes | None:
    """JPEG thumbnail (or None when the payload is not an image)."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.thumbnail((max_width, max_width))
            output = io.BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=82)
            return output.getvalue()
    except Exception:
        return None
