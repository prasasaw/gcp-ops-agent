"""Top GCP services by cost for a project via BigQuery billing export."""

import os
from typing import Optional

from google.cloud import bigquery


def get_top_services_by_cost(project_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: Optional[int] = None) -> dict:
    """Return the top N services by cost for a GCP project between start_date and end_date (YYYY-MM-DD).

    project_id defaults to the GOOGLE_CLOUD_PROJECT env var when not supplied.
    start_date/end_date default to the first and last day of the current month.
    """
    from datetime import date
    project_id = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]
    today = date.today()
    start_date = start_date or today.replace(day=1).isoformat()
    end_date = end_date or today.isoformat()
    limit = limit or 10
    bq_project = os.environ["BILLING_BQ_PROJECT"]
    bq_dataset = os.environ["BILLING_BQ_DATASET"]
    account_suffix = os.environ["BILLING_ACCOUNT_ID"].replace("-", "_")
    table = f"`{bq_project}.{bq_dataset}.gcp_billing_export_v1_{account_suffix}`"

    query = f"""
        WITH costs AS (
            SELECT
                service.description AS service_name,
                SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) AS c), 0)) AS service_cost,
                currency
            FROM {table}
            WHERE
                project.id = @project_id
                AND DATE(_PARTITIONTIME) BETWEEN @start_date AND @end_date
            GROUP BY service_name, currency
        ),
        total AS (SELECT SUM(service_cost) AS grand_total FROM costs)
        SELECT
            c.service_name,
            c.service_cost,
            c.currency,
            ROUND(SAFE_DIVIDE(c.service_cost, t.grand_total) * 100, 2) AS pct_of_total
        FROM costs c, total t
        ORDER BY c.service_cost DESC
        LIMIT @limit
    """

    client = bigquery.Client(project=bq_project)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    rows = list(client.query(query, job_config=job_config).result())

    services = [
        {
            "name": row.service_name,
            "cost": round(row.service_cost, 4),
            "currency": row.currency,
            "pct_of_total": row.pct_of_total,
        }
        for row in rows
    ]

    return {
        "project_id": project_id,
        "start_date": start_date,
        "end_date": end_date,
        "services": services,
    }
