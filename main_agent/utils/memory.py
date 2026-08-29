"""Persistent memory helpers for recording and recalling handled GCP findings.

Uses `VertexAiMemoryBankService` when `AGENT_ENGINE_ID` is set (production),
falling back to `InMemoryMemoryService` + a process-local index for local dev.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import threading
from typing import Any

from google.adk.memory import BaseMemoryService, InMemoryMemoryService
from google.adk.memory.memory_entry import MemoryEntry
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

APP_NAME = os.environ.get("APP_NAME", "gcp_ops_agent")
_DEFAULT_USER = os.environ.get("DEFAULT_USER_ID", "local_user")

MEMORY_TYPE_HANDLED = "handled_finding"

_memory_service_singleton: BaseMemoryService | None = None
_singleton_lock = threading.Lock()

# Fallback structured store for services that don't persist custom_metadata
# (e.g. InMemoryMemoryService). Key: (app_name, user_id, recommendation_name).
_local_index: dict[tuple[str, str, str], dict[str, Any]] = {}
_local_index_lock = threading.Lock()


def get_memory_service() -> BaseMemoryService:
    """Return a process-wide memory service.

    Uses `VertexAiMemoryBankService` when `AGENT_ENGINE_ID` is set, else falls
    back to `InMemoryMemoryService` for local development.
    """
    global _memory_service_singleton
    if _memory_service_singleton is not None:
        return _memory_service_singleton
    with _singleton_lock:
        if _memory_service_singleton is not None:
            return _memory_service_singleton

        agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
        if agent_engine_id:
            from google.adk.memory import VertexAiMemoryBankService

            _memory_service_singleton = VertexAiMemoryBankService(
                project=os.environ["GOOGLE_CLOUD_PROJECT"],
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                agent_engine_id=agent_engine_id,
            )
            logger.info(
                "Memory service: VertexAiMemoryBankService (agent_engine_id=%s)",
                agent_engine_id,
            )
        else:
            _memory_service_singleton = InMemoryMemoryService()
            logger.warning(
                "Memory service: InMemoryMemoryService (fallback — set "
                "AGENT_ENGINE_ID for persistent Memory Bank)."
            )
        return _memory_service_singleton


def _identity(tool_context: Any) -> tuple[str, str]:
    """Best-effort extraction of (app_name, user_id) from a ToolContext."""
    app = APP_NAME
    user = _DEFAULT_USER
    inv = getattr(tool_context, "_invocation_context", None) or getattr(
        tool_context, "invocation_context", None
    )
    if inv is not None:
        app = getattr(inv, "app_name", None) or app
        user = getattr(inv, "user_id", None) or user
    return app, user


def _isoformat_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _build_meta(
    recommendation_name: str,
    action: str,
    recommender_subtype: str | None,
    resource: str | None,
    jira_key: str | None,
    branch_name: str | None,
    note: str | None,
    handled_at: str,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "type": MEMORY_TYPE_HANDLED,
        "recommendation_name": recommendation_name,
        "action": action,
        "handled_at": handled_at,
    }
    if recommender_subtype:
        meta["recommender_subtype"] = recommender_subtype
    if resource:
        meta["resource"] = resource
    if jira_key:
        meta["jira_key"] = jira_key
    if branch_name:
        meta["branch_name"] = branch_name
    if note:
        meta["note"] = note
    return meta


async def write_handled_finding(
    tool_context: Any,
    recommendation_name: str,
    action: str,
    *,
    recommender_subtype: str | None = None,
    resource: str | None = None,
    jira_key: str | None = None,
    branch_name: str | None = None,
    note: str | None = None,
) -> None:
    """Record that a GCP Recommender finding has been handled.

    Silently no-ops if `recommendation_name` is empty so callers can invoke this
    unconditionally from tools that may or may not carry finding context.
    """
    if not recommendation_name:
        return
    app_name, user_id = _identity(tool_context)
    handled_at = _isoformat_utc()
    meta = _build_meta(
        recommendation_name,
        action,
        recommender_subtype,
        resource,
        jira_key,
        branch_name,
        note,
        handled_at,
    )

    subject = jira_key or branch_name or note or action
    sentence = (
        f"Handled GCP finding {recommendation_name} via {action} ({subject}) "
        f"on {handled_at}."
    )

    svc = get_memory_service()
    entry = MemoryEntry(
        content=Content(role="user", parts=[Part(text=sentence)]),
        custom_metadata=meta,
        timestamp=handled_at,
    )
    try:
        await svc.add_memory(
            app_name=app_name,
            user_id=user_id,
            memories=[entry],
            custom_metadata=meta,
        )
        logger.info("Wrote handled_finding to memory: %s", recommendation_name)
    except NotImplementedError:
        logger.info(
            "Memory service does not support add_memory; using local index for %s",
            recommendation_name,
        )
    except Exception:
        logger.exception("Failed to write handled_finding to memory")

    with _local_index_lock:
        _local_index[(app_name, user_id, recommendation_name)] = meta


async def find_handled_finding(
    tool_context: Any,
    recommendation_name: str,
) -> dict[str, Any] | None:
    """Return the most recent handled-finding record for a recommendation, or None."""
    if not recommendation_name:
        return None
    app_name, user_id = _identity(tool_context)

    svc = get_memory_service()
    try:
        response = await svc.search_memory(
            app_name=app_name, user_id=user_id, query=recommendation_name
        )
    except Exception:
        logger.exception("Memory search_memory failed")
        response = None

    matches: list[dict[str, Any]] = []
    if response is not None:
        for entry in getattr(response, "memories", []) or []:
            meta = getattr(entry, "custom_metadata", None) or {}
            if meta.get("type") != MEMORY_TYPE_HANDLED:
                continue
            if meta.get("recommendation_name") != recommendation_name:
                continue
            matches.append(meta)

    if not matches:
        with _local_index_lock:
            fallback = _local_index.get((app_name, user_id, recommendation_name))
        if fallback:
            return fallback
        return None

    matches.sort(key=lambda m: m.get("handled_at", ""), reverse=True)
    return matches[0]
