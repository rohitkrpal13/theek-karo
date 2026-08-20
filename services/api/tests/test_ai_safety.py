"""AI safety tests (Step 12).

Covers tool authorization (``required_role`` enforced at the registry, never
left to handlers) and the daily chat cost cap that bounds per-user AI spend on
top of the per-minute rate limits.
"""

from __future__ import annotations

from tk_api.ai.tools import ToolRegistry
from tk_api.users.models import User


class TestToolAuthorization:
    def test_all_registered_tools_are_public_by_default(self) -> None:  # type: ignore[no-untyped-def]
        """Safety invariant: shipped tools are public-safe (READ_ONLY, no role
        leaks). Explicitly role-gated tools (Phase 19 integration ops) must be
        READ_ONLY and carry an explicit least-privilege role — never "public"
        with restricted data."""
        registry = ToolRegistry()
        for tool in registry.list_tools():
            assert tool["riskLevel"] == "READ_ONLY", tool["name"]
            role = tool["requiredRole"]
            if role != "public":
                assert role in {"admin", "department_manager"}, tool["name"]

    def test_role_guarded_tool_refuses_anonymous_and_underprivileged(self) -> None:  # type: ignore[no-untyped-def]
        import asyncio

        from tk_api.ai.tools import ToolSpec

        registry = ToolRegistry()

        async def _admin_handler(session=None) -> dict:  # type: ignore[no-untyped-def]
            return {"ok": True}

        spec = ToolSpec(
            name="secret_stats",
            description="admin-only tool (test)",
            input_schema={"type": "object", "properties": {}},
            output_schema={},
            handler=_admin_handler,
            required_role="admin",
        )
        registry.register(spec)

        async def run(viewer) -> dict:  # type: ignore[no-untyped-def]
            return await registry.execute(None, "secret_stats", {}, viewer=viewer)  # type: ignore[arg-type]

        blocked = asyncio.run(run(None))
        assert "requires role" in blocked["error"]

        citizen = User(display_name="Citizen", status="active")
        citizen.roles = [type("R", (), {"code": "citizen"})()]  # type: ignore[attr-defined]
        assert "requires role" in asyncio.run(run(citizen))["error"]

        admin = User(display_name="Admin", status="active")
        admin.roles = [type("R", (), {"code": "admin"})()]  # type: ignore[attr-defined]
        assert asyncio.run(run(admin)) == {"ok": True}


class TestDailyChatCap:
    def test_daily_limit_returns_429(self, client) -> None:  # type: ignore[no-untyped-def]
        client.app.state.settings.ai_daily_chat_limit = 3
        body = {"message": "Tell me about schools near Patna"}
        for _ in range(3):
            response = client.post("/api/v1/ai/chat", json=body)
            assert response.status_code == 200, response.text
        limited = client.post("/api/v1/ai/chat", json=body)
        assert limited.status_code == 429
