# Fix Instructions

**Issue:** Create dedicated service account for Cloud Run service gcp-ops-service to increase security
**Affected resource:** //run.googleapis.com/projects/664004376005/regions/europe-west2/services/gcp-ops-service
**Severity:** High

## Recommended remediation

1. Define a new IAM service account (e.g., `gcp-ops-service-sa@prasad-gcp4-project.iam.gserviceaccount.com`).
2. Grant only the necessary IAM permissions/roles required by the `gcp-ops-service` to this service account.
3. Update the Cloud Run service specification (such as Terraform configs or `service.yaml` manifests) to set `serviceAccountName` to the new service account.
4. Deploy the updated configurations so the service no longer runs as the default Compute Engine service account.
