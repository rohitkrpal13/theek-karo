"""Centralized API v1 router registry (API.md §1).

Gathers all domain routers under a versioned `/api/v1` mount point,
allowing future `/api/v2` routers to coexist seamlessly.
"""

from __future__ import annotations

from fastapi import APIRouter

from tk_api.api.routers.ai import ai_router
from tk_api.api.routers.ai_platform import ai_platform_router
from tk_api.api.routers.analytics import analytics_router
from tk_api.api.routers.civic import civic_router
from tk_api.api.routers.civic_actions import civic_action_router
from tk_api.api.routers.communication import communication_router
from tk_api.api.routers.community import community_router
from tk_api.api.routers.data_trust import data_trust_router
from tk_api.api.routers.feed import feed_router
from tk_api.api.routers.geography import geography_router
from tk_api.api.routers.gis import gis_router
from tk_api.api.routers.govdata import govdata_router
from tk_api.api.routers.government import government_router
from tk_api.api.routers.identity import identity_router
from tk_api.api.routers.institutions import institutions_router
from tk_api.api.routers.integrations import integrations_router
from tk_api.api.routers.intelligence import intelligence_router
from tk_api.api.routers.measurement import measurement_router
from tk_api.api.routers.media import media_router
from tk_api.api.routers.notifications import notifications_router
from tk_api.api.routers.production import production_router
from tk_api.api.routers.reports import reports_router
from tk_api.api.routers.search import search_router
from tk_api.api.routers.security import security_router
from tk_api.api.routers.users_auth import auth_router, users_router
from tk_api.cases.router import cases_router
from tk_api.departments.router import departments_router
from tk_api.publicdata.router import publicdata_router
from tk_api.resolution.router import followup_router, resolution_router

api_v1_router = APIRouter()

# Domain routers
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(geography_router)
api_v1_router.include_router(institutions_router)
api_v1_router.include_router(civic_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(media_router)
api_v1_router.include_router(measurement_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(feed_router)
api_v1_router.include_router(community_router)
api_v1_router.include_router(gis_router)
api_v1_router.include_router(govdata_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(departments_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(resolution_router)
api_v1_router.include_router(followup_router)
api_v1_router.include_router(publicdata_router)
api_v1_router.include_router(integrations_router)
api_v1_router.include_router(intelligence_router)
api_v1_router.include_router(civic_action_router)
api_v1_router.include_router(data_trust_router)
api_v1_router.include_router(identity_router)
api_v1_router.include_router(government_router)
api_v1_router.include_router(communication_router)
api_v1_router.include_router(ai_platform_router)
api_v1_router.include_router(security_router)
api_v1_router.include_router(production_router)
