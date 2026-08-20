"""Communication API: alerts, templates, delivery, campaigns, analytics, devices (Phase 26)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from tk_api.api.deps import CurrentUser, DbSession
from tk_api.auth.authorization import require_permission
from tk_api.communication import service as comm_service
from tk_api.communication.models import (
    CommTemplate,
    DeliveryRecord,
    UserDevice,
)
from tk_api.communication.providers import build_providers

communication_router = APIRouter(prefix="/api/v1/communication", tags=["communication"])

DepCommRead = Annotated[Any, Depends(require_permission("government.read"))]
DepCommManage = Annotated[Any, Depends(require_permission("government.manage"))]
DepCommAlert = Annotated[Any, Depends(require_permission("government.manage"))]
DepCommCampaign = Annotated[Any, Depends(require_permission("government.manage"))]


def _parse_id(raw: str, *, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        from tk_api.core.errors import ApiError as AE

        raise AE(f"invalid {kind} id", 422, "invalid_id") from exc


# ---------------------------------------------------------------------------
# Public Alerts
# ---------------------------------------------------------------------------


@communication_router.get("/alerts", summary="List public alerts")
async def list_alerts(
    session: DbSession,
    _user: DepCommRead,
    status: Annotated[str | None, Query()] = None,
    geography_id: Annotated[uuid.UUID | None, Query()] = None,
    include_expired: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    rows = await comm_service.list_alerts(
        session,
        status=status,
        geography_id=geography_id,
        include_expired=include_expired,
        limit=limit,
    )
    return {
        "items": [
            {
                "id": str(a.id),
                "title": a.title,
                "body": a.body,
                "category": a.category,
                "severity": a.severity,
                "status": a.status,
                "source": a.source,
                "verified": a.verified,
                "geography_id": str(a.geography_id) if a.geography_id else None,
                "published_at": a.published_at,
                "expires_at": a.expires_at,
                "created_at": a.created_at,
            }
            for a in rows
        ],
        "count": len(rows),
    }


@communication_router.get("/alerts/{alert_id}", summary="Alert detail")
async def get_alert(
    alert_id: str,
    session: DbSession,
    _user: DepCommRead,
) -> dict[str, Any]:
    alert = await comm_service.get_alert(session, _parse_id(alert_id, kind="alert"))
    return {
        "id": str(alert.id),
        "title": alert.title,
        "body": alert.body,
        "category": alert.category,
        "severity": alert.severity,
        "status": alert.status,
        "source": alert.source,
        "source_url": alert.source_url,
        "geography_id": str(alert.geography_id) if alert.geography_id else None,
        "geojson": alert.geojson,
        "target_levels": alert.target_levels,
        "verified": alert.verified,
        "verified_at": alert.verified_at,
        "published_at": alert.published_at,
        "expires_at": alert.expires_at,
        "resolved_at": alert.resolved_at,
        "created_by": str(alert.created_by),
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


@communication_router.post("/alerts", status_code=201, summary="Create a public alert")
async def create_alert(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommAlert,
) -> dict[str, Any]:
    row = await comm_service.create_alert(
        session,
        title=body["title"],
        body=body["body"],
        category=body["category"],
        severity=body.get("severity", "info"),
        source=body["source"],
        source_url=body.get("source_url"),
        geography_id=uuid.UUID(body["geography_id"]) if body.get("geography_id") else None,
        target_levels=body.get("target_levels"),
        actor_id=user.id,
        expires_at=body.get("expires_at"),
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@communication_router.post(
    "/alerts/{alert_id}/review", summary="Review and publish/reject an alert"
)
async def review_alert(
    alert_id: str,
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommAlert,
) -> dict[str, Any]:
    alert = await comm_service.get_alert(session, _parse_id(alert_id, kind="alert"))
    row = await comm_service.review_alert(
        session,
        alert,
        decision=body["decision"],
        actor_id=user.id,
        note=body.get("note"),
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@communication_router.post("/alerts/{alert_id}/resolve", summary="Resolve a published alert")
async def resolve_alert(
    alert_id: str,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommAlert,
) -> dict[str, Any]:
    alert = await comm_service.get_alert(session, _parse_id(alert_id, kind="alert"))
    row = await comm_service.resolve_alert(session, alert, actor_id=user.id)
    await session.commit()
    return {"id": str(row.id), "status": row.status}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@communication_router.get("/templates", summary="List communication templates")
async def list_templates(
    session: DbSession,
    _user: DepCommRead,
    code: Annotated[str | None, Query()] = None,
    channel: Annotated[str | None, Query()] = None,
    locale: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    rows = await comm_service.list_templates(
        session, code=code, channel=channel, locale=locale, status=status
    )
    return {
        "items": [
            {
                "id": str(t.id),
                "code": t.code,
                "name": t.name,
                "channel": t.channel,
                "locale": t.locale,
                "subject": t.subject,
                "body_text": t.body_text,
                "version": t.version,
                "status": t.status,
                "category": t.category,
                "created_at": t.created_at,
            }
            for t in rows
        ],
        "count": len(rows),
    }


@communication_router.post("/templates", status_code=201, summary="Create a template")
async def create_template(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommManage,
) -> dict[str, Any]:
    row = await comm_service.create_template(
        session,
        code=body["code"],
        name=body["name"],
        channel=body["channel"],
        locale=body.get("locale", "en"),
        subject=body.get("subject"),
        body_text=body.get("body_text", ""),
        body_html=body.get("body_html"),
        variables=body.get("variables"),
        category=body.get("category", "system"),
        created_by=user.id,
    )
    await session.commit()
    return {"id": str(row.id), "code": row.code, "version": row.version}


@communication_router.post("/templates/{template_id}/publish", summary="Publish a template")
async def publish_template(
    template_id: str,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommManage,
) -> dict[str, Any]:

    parsed = _parse_id(template_id, kind="template")
    template = await session.get(CommTemplate, parsed)
    if template is None:
        from tk_api.core.errors import NotFoundError

        raise NotFoundError("template not found", kind="template_not_found")
    row = await comm_service.publish_template(session, template, actor_id=user.id)
    await session.commit()
    return {"id": str(row.id), "status": row.status, "version": row.version}


# ---------------------------------------------------------------------------
# Delivery Records
# ---------------------------------------------------------------------------


@communication_router.get("/deliveries", summary="List delivery records (admin)")
async def list_deliveries(
    session: DbSession,
    _user: DepCommManage,
    channel: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    from sqlalchemy import select

    stmt = select(DeliveryRecord).order_by(DeliveryRecord.created_at.desc())
    if channel:
        stmt = stmt.where(DeliveryRecord.channel == channel)
    if status:
        stmt = stmt.where(DeliveryRecord.status == status)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return {
        "items": [
            {
                "id": str(d.id),
                "notification_id": str(d.notification_id),
                "channel": d.channel,
                "status": d.status,
                "provider": d.provider,
                "attempts": d.attempts,
                "max_attempts": d.max_attempts,
                "delivered_at": d.delivered_at,
                "failed_at": d.failed_at,
                "error": d.error,
                "cost_estimate": float(d.cost_estimate) if d.cost_estimate else None,
                "created_at": d.created_at,
            }
            for d in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# User Devices
# ---------------------------------------------------------------------------


@communication_router.get("/devices", summary="List my devices")
async def list_devices(
    session: DbSession,
    user: CurrentUser,
    include_inactive: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    rows = await comm_service.list_user_devices(session, user.id, include_inactive=include_inactive)
    return {
        "items": [
            {
                "id": str(d.id),
                "platform": d.platform,
                "device_name": d.device_name,
                "is_active": d.is_active,
                "last_active_at": d.last_active_at,
                "created_at": d.created_at,
            }
            for d in rows
        ],
        "count": len(rows),
    }


@communication_router.post("/devices", status_code=201, summary="Register a device")
async def register_device(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    row = await comm_service.register_device(
        session,
        user_id=user.id,
        platform=body["platform"],
        push_token=body["push_token"],
        device_name=body.get("device_name"),
    )
    await session.commit()
    return {"id": str(row.id), "platform": row.platform}


@communication_router.delete("/devices/{device_id}", status_code=204, summary="Revoke a device")
async def revoke_device(
    device_id: str,
    session: DbSession,
    user: CurrentUser,
) -> None:
    parsed = _parse_id(device_id, kind="device")
    device = await session.get(UserDevice, parsed)
    if device is None or device.user_id != user.id:
        from tk_api.core.errors import NotFoundError

        raise NotFoundError("device not found", kind="device_not_found")
    await comm_service.revoke_device(session, device, actor_id=user.id)
    await session.commit()


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------


@communication_router.get("/campaigns", summary="List campaigns")
async def list_campaigns(
    session: DbSession,
    _user: DepCommRead,
    status: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    rows = await comm_service.list_campaigns(session, status=status, category=category)
    return {
        "items": [
            {
                "id": str(c.id),
                "name": c.name,
                "category": c.category,
                "channel": c.channel,
                "status": c.status,
                "estimated_recipients": c.estimated_recipients,
                "sent_count": c.sent_count,
                "delivered_count": c.delivered_count,
                "created_at": c.created_at,
            }
            for c in rows
        ],
        "count": len(rows),
    }


@communication_router.post("/campaigns", status_code=201, summary="Create a campaign")
async def create_campaign(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommCampaign,
) -> dict[str, Any]:
    row = await comm_service.create_campaign(
        session,
        name=body["name"],
        description=body.get("description"),
        category=body.get("category", "community"),
        channel=body["channel"],
        subject=body.get("subject"),
        body=body["body"],
        audience_filter=body.get("audience_filter"),
        actor_id=user.id,
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@communication_router.post("/campaigns/{campaign_id}/approve", summary="Approve a campaign")
async def approve_campaign(
    campaign_id: str,
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommCampaign,
) -> dict[str, Any]:
    campaign = await comm_service.get_campaign(session, _parse_id(campaign_id, kind="campaign"))
    row = await comm_service.approve_campaign(
        session,
        campaign,
        actor_id=user.id,
        estimated_recipients=body.get("estimated_recipients", 0),
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@communication_router.post("/campaigns/{campaign_id}/cancel", summary="Cancel a campaign")
async def cancel_campaign(
    campaign_id: str,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCommCampaign,
) -> dict[str, Any]:
    campaign = await comm_service.get_campaign(session, _parse_id(campaign_id, kind="campaign"))
    row = await comm_service.cancel_campaign(session, campaign, actor_id=user.id)
    await session.commit()
    return {"id": str(row.id), "status": row.status}


# ---------------------------------------------------------------------------
# Analytics & Provider Health
# ---------------------------------------------------------------------------


@communication_router.get("/analytics", summary="Communication analytics")
async def get_analytics(
    session: DbSession,
    _user: DepCommManage,
    channel: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return await comm_service.get_communication_analytics(session, channel=channel)


@communication_router.get("/providers/health", summary="Provider health status")
async def get_provider_health(
    session: DbSession,
    _user: DepCommManage,
) -> dict[str, Any]:
    providers = build_providers()
    results = await comm_service.get_provider_health(session, providers)
    return {"providers": results, "count": len(results)}
