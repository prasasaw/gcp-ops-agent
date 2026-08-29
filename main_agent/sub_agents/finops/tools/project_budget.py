"""Configured budgets for a GCP project via Cloud Billing Budgets API."""

import os
from typing import Optional

from google.cloud.billing import budgets_v1


def get_project_budgets(project_id: Optional[str] = None) -> dict:  # None → reads GOOGLE_CLOUD_PROJECT env var
    """Return all configured budgets for a GCP project.

    project_id defaults to the GOOGLE_CLOUD_PROJECT env var when not supplied.
    Note: the Budgets API returns configured amounts and alert thresholds,
    not real-time spend — use get_project_cost() for actual spend.
    """
    project_id = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]
    billing_account_id = os.environ["BILLING_ACCOUNT_ID"]
    parent = f"billingAccounts/{billing_account_id}"

    client = budgets_v1.BudgetServiceClient()
    request = budgets_v1.ListBudgetsRequest(parent=parent)

    budgets = []
    for budget in client.list_budgets(request=request):
        # Filter to budgets scoped to this project
        scoped = budget.budget_filter.projects
        if scoped and not any(f"projects/{project_id}" in p for p in scoped):
            continue

        amount = budget.amount
        if amount.HasField("specified_amount"):
            budget_amount = amount.specified_amount.units + amount.specified_amount.nanos / 1e9
            currency = amount.specified_amount.currency_code
        elif amount.last_period_amount:
            budget_amount = None  # dynamic: based on last period
            currency = "dynamic"
        else:
            budget_amount = None
            currency = "unknown"

        thresholds = [
            {"percent": t.threshold_percent, "basis": t.spend_basis.name}
            for t in budget.threshold_rules
        ]

        budgets.append({
            "name": budget.display_name,
            "amount": budget_amount,
            "currency": currency,
            "alert_thresholds": thresholds,
            "projects": list(scoped) if scoped else ["all projects on billing account"],
        })

    return {"project_id": project_id, "billing_account": billing_account_id, "budgets": budgets}
