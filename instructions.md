# Fix Instructions

**Issue:** Remove unused IAM role on project 664004376005
**Affected resource:** //cloudresourcemanager.googleapis.com/projects/664004376005
**Severity:** Medium

## Recommended remediation

1. Identify the unused IAM role on resource //cloudresourcemanager.googleapis.com/projects/664004376005.
2. Revoke the binding for this unused role.
3. Update the IaC configuration (e.g. Terraform) if the role is managed via code.
4. Verify deployment and ensure no permission issues arise.
