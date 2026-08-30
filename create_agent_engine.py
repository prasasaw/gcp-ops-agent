import vertexai
from vertexai import agent_engines

PROJECT = "prasad-gcp4-project"
LOCATION = "europe-west2"
STAGING_BUCKET = "gs://prasad-gcp4-project-agent-engine-euw2"

vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=STAGING_BUCKET)

engine = agent_engines.create(display_name="gcp-ops-agent-memory")

print("Full name :", engine.resource_name)
print("AGENT_ENGINE_ID:", engine.resource_name.rsplit("/", 1)[-1])
