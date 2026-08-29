"""End-to-end demo of persistent, cross-session memory in gcp-ops-agent.

Scenario:
 1. Turn A (session_a) — the SecOps agent lists mock findings and "files a Jira"
    for one of them via the write helper.
 2. Session flush — the session is added to memory (as `adk web` would do via
    the after_agent_callback).
 3. Turn B (session_b, brand-new session) — the recommendations tool is called
    again and the previously-handled finding is decorated as `already_handled`
    with the linked Jira key.

Run:
    set GOOGLE_CLOUD_PROJECT=your-project
    set GEMINI_MODEL=gemini-flash-latest
    # Local (in-memory fallback):
    python demo_memory.py
    # Persistent (Vertex AI Memory Bank):
    set AGENT_ENGINE_ID=1234567890
    set GOOGLE_CLOUD_LOCATION=us-central1
    python demo_memory.py
"""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace

from main_agent.utils.memory import (
    find_handled_finding,
    get_memory_service,
    write_handled_finding,
)

APP_NAME = os.environ.get("APP_NAME", "gcp_ops_agent")
USER_ID = os.environ.get("DEFAULT_USER_ID", "demo_user")

MOCK_FINDINGS = [
    {
        "name": (
            "projects/demo/locations/global/recommenders/"
            "google.iam.policy.Recommender/recommendations/rec-iam-001"
        ),
        "subtype": "REMOVE_ROLE",
        "resource": "//iam.googleapis.com/projects/demo/serviceAccounts/backend-svc",
        "priority": "P2",
        "description": "Service account 'backend-svc' has over-permissive IAM bindings.",
    },
    {
        "name": (
            "projects/demo/locations/us-central1/recommenders/"
            "google.run.service.SecurityRecommender/recommendations/rec-run-002"
        ),
        "subtype": "UPDATE_SECURITY_POSTURE",
        "resource": "//run.googleapis.com/projects/demo/locations/us-central1/services/api",
        "priority": "P3",
        "description": "Cloud Run service 'api' should enforce ingress restrictions.",
    },
]


def _fake_tool_context() -> SimpleNamespace:
    """Stand-in for ADK's ToolContext for standalone script runs."""
    return SimpleNamespace(
        _invocation_context=SimpleNamespace(app_name=APP_NAME, user_id=USER_ID),
    )


async def _decorate(findings: list[dict]) -> list[dict]:
    ctx = _fake_tool_context()
    out: list[dict] = []
    for f in findings:
        record = await find_handled_finding(ctx, f["name"])
        entry = dict(f)
        if record:
            entry["status"] = "already_handled"
            entry["previous_action"] = record.get("action")
            entry["handled_at"] = record.get("handled_at")
            if record.get("jira_key"):
                entry["linked_jira"] = record["jira_key"]
            if record.get("branch_name"):
                entry["linked_branch"] = record["branch_name"]
            if record.get("note"):
                entry["handled_note"] = record["note"]
        else:
            entry["status"] = "pending"
        out.append(entry)
    return out


def _summarise(label: str, findings: list[dict]) -> None:
    print(f"\n=== {label} ===")
    for f in findings:
        status = f.get("status", "?").upper()
        extra = ""
        if f.get("linked_jira"):
            extra = f" (Jira: {f['linked_jira']}, at {f['handled_at']})"
        elif f.get("linked_branch"):
            extra = f" (branch: {f['linked_branch']}, at {f['handled_at']})"
        elif f.get("previous_action"):
            extra = f" ({f['previous_action']} at {f['handled_at']})"
        print(f"  [{status}] {f['subtype']} — {f['description']}{extra}")


async def _turn_a_file_jira() -> None:
    ctx = _fake_tool_context()
    target = MOCK_FINDINGS[0]
    fake_jira_key = "SEC-123"
    print(f"\n[Turn A] Simulating create_jira_story for {target['subtype']} → {fake_jira_key}")
    await write_handled_finding(
        ctx,
        recommendation_name=target["name"],
        action="jira",
        recommender_subtype=target["subtype"],
        resource=target["resource"],
        jira_key=fake_jira_key,
    )


async def main() -> None:
    svc = get_memory_service()
    print(f"Memory backend: {type(svc).__name__}")
    print(f"App: {APP_NAME}  User: {USER_ID}")

    # Session A — before anything is handled.
    listing_a = await _decorate(MOCK_FINDINGS)
    _summarise("Session A · initial recommendation listing", listing_a)

    # Turn A — user asks to file a Jira for finding #1.
    await _turn_a_file_jira()

    # Simulate ending the session and starting a fresh one (no shared state).
    print("\n--- Session A ended. Memory persists. Starting Session B... ---")

    # Session B — brand-new session; expect the finding to be tagged.
    listing_b = await _decorate(MOCK_FINDINGS)
    _summarise("Session B · listing after Turn A", listing_b)

    print("\nRaw handled record for the first finding:")
    print(
        json.dumps(
            await find_handled_finding(_fake_tool_context(), MOCK_FINDINGS[0]["name"]),
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
