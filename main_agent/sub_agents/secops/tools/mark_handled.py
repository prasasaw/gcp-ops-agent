"""User-invoked marker: record that a GCP finding has been resolved/snoozed."""

from google.adk.tools import ToolContext

from ....utils.memory import find_handled_finding, write_handled_finding

_ALLOWED_STATUSES = {"resolved", "snoozed", "wont_fix"}


async def mark_finding_handled(
    recommendation_name: str,
    status: str,
    note: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Persist an explicit disposition for a GCP Recommender finding.

    Use this when the user says things like "mark this resolved", "snooze this",
    or "wont fix it" for a specific security recommendation. The record is
    stored in long-term memory so the finding shows up as handled in future
    sessions.

    Args:
        recommendation_name: Full GCP Recommender resource name of the finding
            (e.g. 'projects/.../recommendations/xyz'). Must be an exact match
            for future lookups to work.
        status: One of 'resolved', 'snoozed', 'wont_fix'.
        note: Optional short human-readable justification.

    Returns:
        dict describing the recorded disposition, or an error.
    """
    status = (status or "").strip().lower()
    if status not in _ALLOWED_STATUSES:
        return {
            "error": (
                f"Invalid status '{status}'. Must be one of "
                f"{sorted(_ALLOWED_STATUSES)}."
            )
        }
    if not recommendation_name:
        return {"error": "recommendation_name is required."}

    await write_handled_finding(
        tool_context,
        recommendation_name=recommendation_name,
        action=status,
        note=note,
    )

    stored = await find_handled_finding(tool_context, recommendation_name)
    return {
        "status": "recorded",
        "recommendation_name": recommendation_name,
        "disposition": status,
        "note": note,
        "stored_record": stored,
    }
