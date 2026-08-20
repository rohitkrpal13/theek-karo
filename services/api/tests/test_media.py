"""Media lifecycle tests (API.md §7): upload request (idempotent), dev-mode PUT,
complete with size/checksum/scan-gate verification (jpeg bytes vs. junk), failures
never serve, thumbnail generation, owner-only metadata, replays."""

from __future__ import annotations

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import _register_and_verify
from tk_api.media.storage import MemoryStorageAdapter


@pytest.fixture(autouse=True)
def _memory_storage(client) -> None:  # type: ignore[no-untyped-def]
    """Media unit tests use the in-memory storage adapter (no disk, no MinIO)."""
    client.app.state.storage = MemoryStorageAdapter()
    yield


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user_headers(client: TestClient, sender, phone: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, phone)
    return _auth(tokens["access_token"])


def _jpeg_bytes(size: tuple[int, int] = (640, 480), color: str = "red") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format="JPEG")
    return stream.getvalue()


def _request_upload(client: TestClient, headers: dict[str, str], **overrides) -> dict:  # type: ignore[no-untyped-def]
    payload = {"mime_type": "image/jpeg", "size_bytes": len(_jpeg_bytes())}
    payload.update(overrides)
    response = client.post(
        "/api/v1/media/uploads",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestUploadRequest:
    def test_requires_auth(self, client) -> None:  # type: ignore[no-untyped-def]
        assert (
            client.post(
                "/api/v1/media/uploads", json={"mime_type": "image/jpeg", "size_bytes": 100}
            ).status_code
            == 401
        )

    def test_unsupported_mime_and_size(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _user_headers(client, sender, "9876544100")
        bad_mime = client.post(
            "/api/v1/media/uploads",
            headers=headers,
            json={"mime_type": "application/pdf", "size_bytes": 100},
        )
        assert bad_mime.status_code == 422
        assert bad_mime.json()["type"].endswith("/unsupported_mime")
        oversize = client.post(
            "/api/v1/media/uploads",
            headers=headers,
            json={"mime_type": "image/jpeg", "size_bytes": 9 * 1024 * 1024},
        )
        assert oversize.status_code == 422
        assert oversize.json()["type"].endswith("/invalid_size")

    def test_request_and_idempotent_replay(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _user_headers(client, sender, "9876544101")
        key = str(uuid.uuid4())
        data = _jpeg_bytes()
        first = client.post(
            "/api/v1/media/uploads",
            headers={**headers, "Idempotency-Key": key},
            json={"mime_type": "image/jpeg", "size_bytes": len(data)},
        )
        assert first.status_code == 201
        assert first.json()["upload_method"] == "api"  # memory storage → API route
        assert first.json()["presigned_url"] is None
        replay = client.post(
            "/api/v1/media/uploads",
            headers={**headers, "Idempotency-Key": key},
            json={"mime_type": "image/jpeg", "size_bytes": len(data)},
        )
        assert replay.status_code == 200
        assert replay.json()["media_id"] == first.json()["media_id"]


class TestUploadLifecycle:
    def _upload(
        self, client, sender, phone: str, data: bytes | None = None
    ) -> tuple[dict, dict[str, str]]:  # type: ignore[no-untyped-def]
        data = data if data is not None else _jpeg_bytes()
        headers = _user_headers(client, sender, phone)
        upload = _request_upload(client, headers, size_bytes=len(data))
        return upload, headers

    def test_complete_happy_path_with_thumbnail(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        upload, headers = self._upload(client, sender, "9876544102")
        put = client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers={**headers, "Content-Type": "image/jpeg"},
            content=_jpeg_bytes(),
        )
        assert put.status_code == 204
        complete = client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
        assert complete.status_code == 200, complete.text
        body = complete.json()
        assert body["status"] == "available"
        assert body["scan_status"] == "clean"
        assert body["width"] == 640
        assert body["height"] == 480
        assert body["mime_type"] == "image/jpeg"
        assert body["download_url"].startswith("/api/v1/media/object/")

        # replay returns the same final state (idempotent complete)
        replay = client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
        assert replay.status_code == 200
        assert replay.json()["status"] == "available"

        # thumbnail route (unattached media requires the owner)
        thumb = client.get(f"/api/v1/media/{upload['media_id']}/thumbnail", headers=headers)
        assert thumb.status_code == 200
        assert thumb.headers["content-type"] == "image/jpeg"
        assert len(thumb.content) > 0

    def test_checksum_verified(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        data = _jpeg_bytes()
        upload, headers = self._upload(client, sender, "9876544103", data=data)
        client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=data,
        )
        wrong = client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={"checksum_sha256": "0" * 64},
        )
        assert wrong.status_code == 409
        assert wrong.json()["type"].endswith("/checksum_mismatch")
        # failed media never serves: subsequent metadata access is refused
        failed = client.get(f"/api/v1/media/{upload['media_id']}", headers=headers)
        assert failed.status_code == 409
        assert failed.json()["type"].endswith("/media_failed")

    def test_scan_gate_blocks_junk(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        junk = b"this is definitely not an image"
        upload, headers = self._upload(client, sender, "9876544104", data=junk)
        client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=junk,
        )
        complete = client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
        assert complete.status_code == 422
        assert complete.json()["type"].endswith("/scan_failed")
        # failed media never serves
        assert client.get(f"/api/v1/media/{upload['media_id']}", headers=headers).status_code == 409

    def test_size_mismatch_and_missing_object(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        data = _jpeg_bytes()
        upload, headers = self._upload(client, sender, "9876544105", data=data)
        put = client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=data[:100],
        )
        assert put.status_code == 409
        assert put.json()["type"].endswith("/size_mismatch")

        upload2, headers2 = self._upload(client, sender, "9876544106", data=data)
        missing = client.post(
            f"/api/v1/media/uploads/{upload2['media_id']}/complete",
            headers={**headers2, "Content-Type": "application/json"},
            json={},
        )
        assert missing.status_code == 409
        assert missing.json()["type"].endswith("/upload_missing")

    def test_owner_only_metadata(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        upload, headers = self._upload(client, sender, "9876544107")
        data = _jpeg_bytes()
        client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=data,
        )
        client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
        stranger = _user_headers(client, sender, "9876544108")
        assert (
            client.get(f"/api/v1/media/{upload['media_id']}", headers=stranger).status_code == 403
        )


class TestUploadHardening:
    """Step 6: stronger scan gate, malformed-body handling, rate limits,
    body-size pre-checks, and safe download headers."""

    def _upload(  # type: ignore[no-untyped-def]
        self, client, sender, phone: str, data: bytes | None = None
    ) -> tuple[dict, dict[str, str]]:
        data = data if data is not None else _jpeg_bytes()
        headers = _user_headers(client, sender, phone)
        upload = _request_upload(client, headers, size_bytes=len(data))
        return upload, headers

    def _spoof_webp(self) -> bytes:
        # RIFF container but NOT a WEBP fourcc (e.g. WAVE) — must fail the gate
        return b"RIFF" + b"\x1c\x00\x00\x00" + b"WAVE" + b"\x00" * 20

    def _html_polyglot(self) -> bytes:
        # JPEG magic bytes followed by an HTML payload — must fail decodability
        return b"\xff\xd8\xff\xe0" + b"<html><script>alert(1)</script></html>" + b"\x00" * 16

    def _huge_png(self) -> bytes:
        # 1x1 PNG whose IHDR declares 40000x40000 → decompression bomb
        stream = io.BytesIO()
        Image.new("RGB", (1, 1), "red").save(stream, format="PNG")
        data = bytearray(stream.getvalue())
        data[16:20] = (40000).to_bytes(4, "big")  # IHDR width
        data[20:24] = (40000).to_bytes(4, "big")  # IHDR height
        return bytes(data)

    def _upload_and_complete(self, client, sender, phone: str, data: bytes, mime: str):  # type: ignore[no-untyped-def]
        headers = _user_headers(client, sender, phone)
        upload = _request_upload(client, headers, mime_type=mime, size_bytes=len(data))
        client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=data,
        )
        return client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )

    def test_webp_spoof_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        data = self._spoof_webp()
        complete = self._upload_and_complete(client, sender, "9876544109", data, "image/webp")
        assert complete.status_code == 422
        assert complete.json()["type"].endswith("/scan_failed")

    def test_html_polyglot_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        data = self._html_polyglot()
        complete = self._upload_and_complete(client, sender, "9876544110", data, "image/jpeg")
        assert complete.status_code == 422
        assert complete.json()["type"].endswith("/scan_failed")

    def test_decompression_bomb_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        data = self._huge_png()
        complete = self._upload_and_complete(client, sender, "9876544111", data, "image/png")
        assert complete.status_code == 422
        assert complete.json()["type"].endswith("/scan_failed")

    def test_invalid_json_body_is_422(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _user_headers(client, sender, "9876544112")
        response = client.post(
            "/api/v1/media/uploads",
            headers={**headers, "Content-Type": "application/json"},
            content=b"{not valid json",
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_payload")

    def test_upload_request_rate_limited(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _user_headers(client, sender, "9876544113")
        payload = {"mime_type": "image/jpeg", "size_bytes": 100}
        for _ in range(30):
            assert (
                client.post(
                    "/api/v1/media/uploads",
                    headers={**headers, "Content-Type": "application/json"},
                    json=payload,
                ).status_code
                == 201
            )
        limited = client.post(
            "/api/v1/media/uploads",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
        )
        assert limited.status_code == 429

    def test_oversized_dev_put_rejected_before_buffering(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        upload, headers = self._upload(client, sender, "9876544114")
        put = client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=b"x" * (8 * 1024 * 1024 + 1),
        )
        assert put.status_code == 413
        assert put.json()["type"].endswith("/payload_too_large")

    def test_safe_download_headers(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        upload, headers = self._upload(client, sender, "9876544115")
        data = _jpeg_bytes()
        client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=data,
        )
        complete = client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
        assert complete.status_code == 200
        url = complete.json()["download_url"]
        # unattached media requires the owner (Phase 16 visibility gate)
        obj = client.get(url, headers=headers)
        assert obj.status_code == 200
        assert obj.headers["x-content-type-options"] == "nosniff"
        disposition = obj.headers["content-disposition"]
        assert disposition.startswith("inline")
        assert disposition.endswith('.jpg"')
        thumb = client.get(f"/api/v1/media/{upload['media_id']}/thumbnail", headers=headers)
        assert thumb.headers["x-content-type-options"] == "nosniff"
        assert "thumb-" in thumb.headers["content-disposition"]

    def test_evidence_download_route_streams_with_gate(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        """Evidence ``url`` links resolve: owner streams bytes, a stranger gets
        404 for unattached media (Step 7)."""
        upload, headers = self._upload(client, sender, "9876544116")
        data = _jpeg_bytes()
        client.put(
            f"/api/v1/media/uploads/{upload['media_id']}/object",
            headers=headers,
            content=data,
        )
        complete = client.post(
            f"/api/v1/media/uploads/{upload['media_id']}/complete",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
        assert complete.status_code == 200
        media_id = upload["media_id"]
        url = f"/api/v1/media/{media_id}/download"
        assert client.get(url).status_code == 404  # anonymous: hidden
        owner = client.get(url, headers=headers)
        assert owner.status_code == 200
        assert owner.headers["content-type"] == "image/jpeg"
        assert owner.headers["x-content-type-options"] == "nosniff"
        stranger = _user_headers(client, sender, "9876544117")
        assert client.get(url, headers=stranger).status_code == 404
        assert client.get(f"/api/v1/media/{upload['media_id']}", headers=headers).status_code == 200
