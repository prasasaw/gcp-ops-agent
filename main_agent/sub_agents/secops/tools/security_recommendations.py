"""Security recommendations via the GCP Recommender API."""

import os

from google.adk.tools import ToolContext
from google.cloud import recommender_v1

from main_agent.utils.memory import find_handled_finding

_GLOBAL_RECOMMENDERS = [
    "google.iam.policy.Recommender",
]
_REGIONAL_RECOMMENDERS = [
    "google.run.service.IdentityRecommender",
    "google.run.service.SecurityRecommender",
]


async def get_security_recommendations(
    project_id: str | None = None,
    locations: list[str] | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Return active security recommendations for a GCP project.

    Each recommendation is annotated with a ``status`` of ``already_handled``
    (when a prior handled_finding record exists in memory) or ``pending``.
    Handled items also carry ``previous_action``, ``linked_jira``,
    ``linked_branch``, ``handled_at``, and ``handled_note`` where available.

    locations: explicit list of regions (e.g. ['us-central1']). Falls back to
    PROJECT_LOCATION env var (comma-separated) or skips regional recommenders.
    """
    project_id = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]

    if locations is None:
        env_locs = os.environ.get("PROJECT_LOCATION", "")
        locations = [loc.strip() for loc in env_locs.split(",") if loc.strip()]

    client = recommender_v1.RecommenderClient()
    recommendations: list[dict] = []

    def _fetch(recommender_id: str, location: str) -> None:
        parent = (
            f"projects/{project_id}/locations/{location}"
            f"/recommenders/{recommender_id}"
        )
        try:
            for rec in client.list_recommendations(parent=parent):
                if rec.state_info.state != recommender_v1.RecommendationStateInfo.State.ACTIVE:
                    continue
                operations = []
                for og in rec.content.operation_groups:
                    for op in og.operations:
                        operations.append({
                            "action": op.action,
                            "resource": op.resource,
                            "path": op.path,
                        })
                recommendations.append({
                    "recommender": recommender_id,
                    "location": location,
                    "name": rec.name,
                    "description": rec.description,
                    "subtype": rec.recommender_subtype,
                    "priority": rec.priority.name,
                    "operations": operations,
                })
        except Exception as e:  # noqa: BLE001 — surface API errors as data, not exceptions
            recommendations.append({
                "recommender": recommender_id,
                "location": location,
                "error": str(e),
            })

    for recommender_id in _GLOBAL_RECOMMENDERS:
        _fetch(recommender_id, "global")

    for location in locations:
        for recommender_id in _REGIONAL_RECOMMENDERS:
            _fetch(recommender_id, location)

    pending_count = 0
    handled_count = 0
    for rec in recommendations:
        if "error" in rec:
            continue
        handled = await find_handled_finding(tool_context, rec.get("name", ""))
        if handled:
            rec["status"] = "already_handled"
            rec["previous_action"] = handled.get("action")
            rec["handled_at"] = handled.get("handled_at")
            if handled.get("jira_key"):
                rec["linked_jira"] = handled["jira_key"]
            if handled.get("branch_name"):
                rec["linked_branch"] = handled["branch_name"]
            if handled.get("note"):
                rec["handled_note"] = handled["note"]
            handled_count += 1
        else:
            rec["status"] = "pending"
            pending_count += 1

    return {
        "project_id": project_id,
        "locations_queried": ["global"] + locations,
        "total_active_recommendations": pending_count + handled_count,
        "pending_count": pending_count,
        "already_handled_count": handled_count,
        "recommendations": recommendations,
    }
