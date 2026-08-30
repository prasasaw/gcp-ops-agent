# GCP Engineering Agent

A multi-agent system built with Google ADK that helps developers and engineering managers interact with Google Cloud directly from Slack. It surfaces FinOps and security insights, and can automatically create Jira tickets and GitHub fix branches from GCP findings.

## Agents

- **Root Agent** (`gcp_agent`) — SRE manager that delegates to specialist sub-agents
- **FinOps Agent** — GCP costs, budgets, billing anomalies, quota enforcement
- **SecOps Agent** — Security incidents, IAM issues, SCC findings, and proactive recommendations

## Tools

- `create_jira_story` — Creates a Jira ticket from a GCP finding (records it in memory as *handled*)
- `create_fix_branch` — Creates a GitHub fix branch with remediation context (records it in memory as *handled*)
- `mark_finding_handled` — User-invoked disposition for a finding (`resolved` / `snoozed` / `wont_fix`)
- `get_security_recommendations` — Lists active Recommender findings, decorated with *pending* / *already_handled* status

## Long-running memory (Vertex AI Memory Bank)

The agent uses ADK's [`MemoryService`](https://adk.dev/sessions/memory/) to persist **which
GCP Recommender findings have already been handled** across sessions. When a Jira story or
GitHub fix branch is filed against a specific finding — or when the user explicitly marks it
resolved / snoozed / wont_fix — the finding is written to long-term memory. The next time
`get_security_recommendations` runs (in a **brand new** session), those items come back
tagged `already_handled` with the linked Jira key or branch name, so the agent skips
remediation and just cites the prior action.

Backend selection (in `main_agent/utils/memory.py`):

| Env `AGENT_ENGINE_ID` | Memory service used |
|---|---|
| set | `VertexAiMemoryBankService` (persistent, managed by Vertex AI Agent Engine) |
| unset | `InMemoryMemoryService` + process-local index (local dev fallback) |

### Provision an Agent Runtime for Memory Bank

```cmd
gcloud auth application-default login
gcloud config set project %GOOGLE_CLOUD_PROJECT%
:: create the Agent Runtime (one-time); capture the numeric ID from the output
gcloud beta agents runtimes create --display-name=gcp-ops-agent --location=%GOOGLE_CLOUD_LOCATION%
:: then, for every process that should read/write the same memory:
SET AGENT_ENGINE_ID=<numeric id>
```

## Setup

```cmd
pip install -r main_agent/requirements.txt
```

> The deployable dependency list lives inside the agent folder so `adk deploy cloud_run`
> picks it up automatically (it looks for `requirements.txt` next to `agent.py`). There is
> intentionally no second copy at the repo root.

Required env vars for local runs:

```cmd
SET GEMINI_MODEL=gemini-3.5-flash
SET GOOGLE_CLOUD_PROJECT=your-project
SET GOOGLE_CLOUD_LOCATION=europe-west2
:: optional — enables persistent Memory Bank; without it, local InMemory fallback is used
SET AGENT_ENGINE_ID=5598757189100503040
```

## Running locally

```cmd
adk run main_agent
```

With the ADK web UI (wires the memory service into the runner automatically):

```cmd
adk web main_agent --memory_service_uri=agentengine://%AGENT_ENGINE_ID%
```

## Demo the memory feature

A scripted, dependency-free walkthrough is included:

```cmd
python demo_memory.py
```

It runs two "sessions" back-to-back against mock findings:

1. Session A lists findings as *pending*, then simulates filing a Jira for finding #1.
2. Session B (fresh session) lists the same findings — finding #1 is now tagged
   *already_handled* with the Jira key, without any state being passed between sessions.

Set `AGENT_ENGINE_ID` to run the same demo against a real Vertex AI Memory Bank; unset it
to use the in-process fallback.

### Manual demo via `adk web`

1. `adk web main_agent --memory_service_uri=agentengine://%AGENT_ENGINE_ID%`
2. Start Session A → *"list our IAM security recommendations"* → *"file a Jira story for the first one"*.
3. Open a **new** browser session (or restart the process for maximum drama).
4. In Session B → *"list our IAM security recommendations"* → the first finding is
   grouped under *Already handled* with the Jira key from Session A.

## Deploy to GCP

Set once per shell:

```cmd
SET GOOGLE_CLOUD_PROJECT=prasad-gcp4-project
SET GOOGLE_CLOUD_LOCATION=europe-west2
SET SERVICE_NAME=gcp-ops-service
SET APP_NAME=gcp_ops_agent
SET AGENT_PATH=./main_agent
SET GEMINI_MODEL=gemini-3.5-flash
SET AGENT_ENGINE_ID=5598757189100503040
```

Build, push, and set env vars in one command. Everything after `--` is forwarded to
`gcloud run deploy`:

```cmd
adk deploy cloud_run --project=%GOOGLE_CLOUD_PROJECT% --region=%GOOGLE_CLOUD_LOCATION% --service_name=%SERVICE_NAME% --app_name %APP_NAME% --with_ui %AGENT_PATH% ^
  -- --set-env-vars=GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=%GOOGLE_CLOUD_PROJECT%,GOOGLE_CLOUD_LOCATION=%GOOGLE_CLOUD_LOCATION%,GEMINI_MODEL=%GEMINI_MODEL%,AGENT_ENGINE_ID=%AGENT_ENGINE_ID%,PROJECT_LOCATION=%GOOGLE_CLOUD_LOCATION%
```

> `main_agent/.env` is excluded from the deployed image by `.gitignore` (Cloud Build honors
> it), so the container has no env vars unless you pass them here. Every re-deploy replaces
> the full env list on the new revision.

Verify the running revision has the env applied:

```cmd
gcloud run services describe %SERVICE_NAME% --region=%GOOGLE_CLOUD_LOCATION% --project=%GOOGLE_CLOUD_PROJECT% --format="value(status.latestReadyRevisionName)"
gcloud run revisions describe <revision-name-from-above> --region=%GOOGLE_CLOUD_LOCATION% --project=%GOOGLE_CLOUD_PROJECT% --format="value(spec.containers[0].env)"
```

> Note: persistent chat continuity across Cloud Run restarts (in-flight conversation resume)
> would require a persistent `SessionService` (e.g. `DatabaseSessionService` on Cloud SQL) —
> deferred as a follow-up. Memory Bank alone already delivers the "recall handled findings
> across brand-new sessions" story that this PoC targets.


 