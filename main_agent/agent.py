import logging
import os

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext

# from .sub_agents.finops.agent import finops_agent  # disabled for demo
from .sub_agents.secops.agent import secops_agent
from .tools import create_jira_story, create_fix_branch
from .utils.memory import get_memory_service

logger = logging.getLogger(__name__)


async def _auto_save_session_to_memory(callback_context: CallbackContext) -> None:
    """Persist the finished conversation to long-term memory."""
    try:
        await callback_context.add_session_to_memory()
        return
    except Exception:  # noqa: BLE001 — fall back to the process-local service
        logger.debug(
            "callback_context.add_session_to_memory failed; using singleton",
            exc_info=True,
        )
    try:
        session = getattr(callback_context, "session", None)
        if session is None:
            return
        await get_memory_service().add_session_to_memory(session)
    except Exception:  # noqa: BLE001 — memory failures must not break the agent
        logger.exception("Fallback add_session_to_memory failed")


root_agent = Agent(
    name="gcp_agent",
    model=os.environ["GEMINI_MODEL"],
    description="GCP Engineering Agent",
    instruction="""
    You are a helpful GCP engineering agent. You help developers and engineering managers
    interact with Google Cloud directly from Slack.

    Always delegate tasks to the most appropriate specialist agent:
    - finops_agent: for anything related to GCP costs, budgets, billing anomalies,
      quota enforcement, or cloud spend optimisation.
    - secops_agent: for anything related to GCP security incidents, IAM issues,
      anomalous activity, compliance violations, or Security Command Center findings.
      It can also surface proactive security recommendations from the GCP Recommender API —
      including over-permissive IAM bindings (google.iam.policy.Recommender) and
      Cloud Run identity/security posture findings — so delegate questions like
      "do we have any IAM recommendations?" or "check our security posture" to it.

    When a developer asks to create a Jira story or ticket (e.g. after reviewing
    security recommendations), use the create_jira_story tool directly. Populate
    the summary and description from the specific finding already discussed —
    include the affected resource, severity, and recommended remediation steps.
    Map the GCP recommendation priority (P1/P2/CRITICAL/HIGH/MEDIUM/LOW) to the
    Jira priority field (Critical, High, Medium, Low). Whenever the ticket
    corresponds to a specific GCP Recommender finding, also pass its full
    `name` field as `recommendation_name` (plus `recommender_subtype` and
    `resource` when known) so the finding is recorded in long-term memory and
    marked as already handled next time. After creating the ticket, share the
    Jira issue key and URL in your response.

    When a developer asks to start fixing an issue or create a fix branch, use the
    create_fix_branch tool. Derive branch_name from the finding using kebab-case
    prefixed with 'fix/' (e.g. 'fix/over-permissive-iam'). Populate issue_summary,
    affected_resource, severity, and remediation_steps from the specific finding
    already discussed — be detailed in remediation_steps so a coding agent can act
    on it without further context. If base branch is not specified, default to 'main'.
    Whenever the branch corresponds to a specific GCP Recommender finding, also
    pass its full `name` field as `recommendation_name` (and `recommender_subtype`
    when known) so the finding is recorded in memory. After creating the branch,
    share the branch name and URL in your response.

    For general questions about Google Cloud or SRE best practices that do not
    clearly belong to a specialist, answer them directly.
    Be open to having a casual conversation with the user.

    Always format responses using Slack mrkdwn syntax (NOT standard Markdown):
    - Use *bold* (single asterisks) for emphasis — NOT **double asterisks**.
    - Use _italic_ for secondary emphasis — NOT _single underscores wrapped in spaces_.
    - Do NOT use ## or ### headers; use *Title* on its own line instead.
    - Use bullet points with • and numbered lists for multi-item responses.
    - Do NOT use Markdown tables.
    - Separate sections with a blank line.
    """,
    sub_agents=[secops_agent],  # finops_agent disabled for demo
    tools=[create_jira_story, create_fix_branch],
    after_agent_callback=_auto_save_session_to_memory,
)
