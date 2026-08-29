"""Shared Jira action tool — creates issues from security/ops findings."""

import requests
from google.adk.tools import ToolContext

from main_agent.utils.memory import write_handled_finding
from main_agent.utils.secrets import get_secret


async def create_jira_story(
    summary: str,
    description: str,
    priority: str | None = "Medium",
    issue_type: str | None = "Story",
    recommendation_name: str | None = None,
    recommender_subtype: str | None = None,
    resource: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Create a Jira issue and return its key and URL.

    Args:
        summary: One-line issue title.
        description: Full issue body (plain text; will be wrapped in Jira doc format).
        priority: Jira priority name — Critical, High, Medium, or Low.
        issue_type: Jira issue type — Story, Bug, or Task.
        recommendation_name: Full GCP Recommender resource name of the finding
            being remediated (e.g. 'projects/.../recommendations/xyz'). Pass
            this whenever the ticket is filed against a specific Recommender
            finding so it can be flagged as already-handled next time.
        recommender_subtype: Optional Recommender subtype (e.g. 'REMOVE_ROLE').
        resource: Optional GCP resource identifier the finding affects.

    Returns:
        dict with keys: key, url, status. On failure: error.
    """
    base_url = get_secret("JIRA_BASE_URL").rstrip("/")
    email = get_secret("JIRA_EMAIL")
    token = get_secret("JIRA_API_TOKEN")
    project_key = get_secret("JIRA_PROJECT_KEY")

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
    }

    resp = requests.post(
        f"{base_url}/rest/api/3/issue",
        json=payload,
        auth=(email, token),
        headers={"Accept": "application/json"},
        timeout=10,
    )

    if not resp.ok:
        return {"error": f"Jira API error {resp.status_code}: {resp.text}"}

    data = resp.json()
    key = data["key"]

    if recommendation_name:
        await write_handled_finding(
            tool_context,
            recommendation_name=recommendation_name,
            action="jira",
            recommender_subtype=recommender_subtype,
            resource=resource,
            jira_key=key,
        )

    return {
        "key": key,
        "url": f"{base_url}/browse/{key}",
        "status": "created",
    }
