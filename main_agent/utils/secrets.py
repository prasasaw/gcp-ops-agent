"""Utilities for resolving secrets from GCP Secret Manager."""

import os

from google.cloud import secretmanager


def get_secret(secret_id: str, project_id: str | None = None, version: str = "latest") -> str:
    """Fetch a secret value from GCP Secret Manager."""
    project = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
