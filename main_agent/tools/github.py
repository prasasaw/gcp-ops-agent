"""GitHub tool — creates a fix branch with an instructions.md commit."""

import base64

import requests
from google.adk.tools import ToolContext

from ..utils.memory import write_handled_finding
from ..utils.secrets import get_secret


async def create_fix_branch(
    branch_name: str,
    issue_summary: str,
    affected_resource: str,
    severity: str,
    remediation_steps: str,
    base: str | None = "main",
    recommendation_name: str | None = None,
    recommender_subtype: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Create a branch from base and commit an instructions.md summarising the finding.

    Args:
        branch_name: New branch name, e.g. 'fix/over-permissive-iam'.
        issue_summary: One-line description of the finding.
        affected_resource: GCP resource identifier (project, service account, etc.).
        severity: Finding severity — Critical, High, Medium, or Low.
        remediation_steps: Step-by-step fix instructions for the coding agent.
        base: Branch to cut from. Defaults to 'main'.
        recommendation_name: Full GCP Recommender resource name of the finding
            being remediated (e.g. 'projects/.../recommendations/xyz'). Pass
            this whenever the branch is cut against a specific Recommender
            finding so it can be flagged as already-handled next time.
        recommender_subtype: Optional Recommender subtype (e.g. 'REMOVE_ROLE').

    Returns:
        dict with keys: branch, url, status. On failure: error.
    """
    token = get_secret("GITHUB_TOKEN")
    repo = get_secret("GITHUB_REPO")  # format: "owner/repo"

    api = "https://api.github.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def _get(path: str) -> requests.Response:
        return requests.get(f"{api}/repos/{repo}/{path}", headers=headers, timeout=10)

    def _post(path: str, payload: dict) -> requests.Response:
        return requests.post(f"{api}/repos/{repo}/{path}", json=payload, headers=headers, timeout=10)

    # a. tip commit SHA of base branch
    r = _get(f"git/ref/heads/{base}")
    if not r.ok:
        return {"error": f"Could not resolve base branch '{base}': {r.status_code} {r.text}"}
    base_commit_sha = r.json()["object"]["sha"]

    # b. tree SHA of base commit
    r = _get(f"git/commits/{base_commit_sha}")
    if not r.ok:
        return {"error": f"Could not fetch base commit: {r.status_code} {r.text}"}
    base_tree_sha = r.json()["tree"]["sha"]

    # c. blob for instructions.md
    instructions = (
        f"# Fix Instructions\n\n"
        f"**Issue:** {issue_summary}\n"
        f"**Affected resource:** {affected_resource}\n"
        f"**Severity:** {severity}\n\n"
        f"## Recommended remediation\n\n"
        f"{remediation_steps}\n"
    )
    r = _post("git/blobs", {
        "content": base64.b64encode(instructions.encode()).decode(),
        "encoding": "base64",
    })
    if not r.ok:
        return {"error": f"Could not create blob: {r.status_code} {r.text}"}
    blob_sha = r.json()["sha"]

    # d. new tree containing instructions.md
    r = _post("git/trees", {
        "base_tree": base_tree_sha,
        "tree": [{"path": "instructions.md", "mode": "100644", "type": "blob", "sha": blob_sha}],
    })
    if not r.ok:
        return {"error": f"Could not create tree: {r.status_code} {r.text}"}
    new_tree_sha = r.json()["sha"]

    # e. commit
    r = _post("git/commits", {
        "message": f"chore: add fix instructions for {issue_summary}",
        "tree": new_tree_sha,
        "parents": [base_commit_sha],
    })
    if not r.ok:
        return {"error": f"Could not create commit: {r.status_code} {r.text}"}
    new_commit_sha = r.json()["sha"]

    # f. create branch ref
    r = _post("git/refs", {"ref": f"refs/heads/{branch_name}", "sha": new_commit_sha})
    if not r.ok:
        return {"error": f"Could not create branch: {r.status_code} {r.text}"}

    branch_url = f"https://github.com/{repo}/tree/{branch_name}"

    if recommendation_name:
        await write_handled_finding(
            tool_context,
            recommendation_name=recommendation_name,
            action="branch",
            recommender_subtype=recommender_subtype,
            resource=affected_resource,
            branch_name=branch_name,
        )

    return {"branch": branch_name, "url": branch_url, "status": "created"}
