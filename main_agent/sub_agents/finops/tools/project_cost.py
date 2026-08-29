"""Total cost for a GCP project via BigQuery billing export."""

import os
from datetime import date
from typing import Optional

from google.cloud import bigquery


def get_project_cost(project_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """Return total cost for a GCP project between start_date and end_date (YYYY-MM-DD).

    project_id defaults to the GOOGLE_CLOUD_PROJECT env var when not supplied.
    start_date/end_date default to the first and last day of the current month.
    Requires BQ billing export to be enabled. Configure via env vars:
      BILLING_BQ_PROJECT, BILLING_BQ_DATASET, BILLING_ACCOUNT_ID
    """
    project_id = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]
    today = date.today()
    start_date = start_date or today.replace(day=1).isoformat()
    end_date = end_date or today.isoformat()
    bq_project = os.environ["BILLING_BQ_PROJECT"]
    bq_dataset = os.environ["BILLING_BQ_DATASET"]
    # Billing account ID format: XXXXXX-XXXXXX-XXXXXX → table suffix uses underscores
    account_suffix = os.environ["BILLING_ACCOUNT_ID"].replace("-", "_")
    table = f"`{bq_project}.{bq_dataset}.gcp_billing_export_v1_{account_suffix}`"

    query = f"""
        SELECT
            SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) AS c), 0)) AS total_cost,
            currency
        FROM {table}
        WHERE
            project.id = @project_id
            AND DATE(_PARTITIONTIME) BETWEEN @start_date AND @end_date
        GROUP BY currency
    """

    client = bigquery.Client(project=bq_project)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        ]
    )

    rows = list(client.query(query, job_config=job_config).result())

    if not rows:
        return {"project_id": project_id, "total_cost": 0.0, "currency": "USD", "start_date": start_date, "end_date": end_date}

    row = rows[0]
    return {
        "project_id": project_id,
        "total_cost": round(row.total_cost, 4),
        "currency": row.currency,
        "start_date": start_date,
        "end_date": end_date,
    }
