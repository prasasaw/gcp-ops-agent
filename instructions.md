# Fix Instructions

**Issue:** Create dedicated service account for Cloud Run service gcp-ops-service
**Affected resource:** //run.googleapis.com/projects/664004376005/regions/europe-west2/services/gcp-ops-service
**Severity:** High

## Recommended remediation

1. Identify the configuration or code repo that defines the Cloud Run service `gcp-ops-service` (located in `europe-west2`).
2. Declare a new Google Cloud Service Account specific to this service, e.g. `gcp-ops-service-sa`.
3. Give the new service account only the minimum required IAM permissions it needs to function (e.g., Datastore, Cloud Storage, or Logging), avoiding broad default roles.
4. Update the Cloud Run service's identity template configuration to use this newly created service account.
5. Deploy or apply the changes (via Terraform or gcloud) to enforce the dedicated identity and resolve the security finding.
