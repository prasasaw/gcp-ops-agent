"""Phase 2: right-sizing recommendations via the GCP Recommender API."""

import os
from typing import Optional

from google.cloud import recommender_v1

_ZONAL_RECOMMENDERS = [
    "google.compute.instance.MachineTypeRecommender",
]
_REGIONAL_RECOMMENDERS = [
    "google.cloudsql.instance.OverprovisionedRecommender",
    "google.run.service.CostRecommender",
]


def get_rightsizing_recommendations(
    project_id: Optional[str] = None,
    locations: Optional[list[str]] = None,
) -> dict:
    """Return active right-sizing recommendations for a GCP project.

    locations: explicit list of zones/regions (e.g. ['us-central1-a', 'us-central1']).
    Falls back to PROJECT_LOCATION env var (comma-separated) or skips location-scoped recommenders.
    """
    project_id = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]

    if locations is None:
        env_locs = os.environ.get("PROJECT_LOCATION", "")
        locations = [l.strip() for l in env_locs.split(",") if l.strip()]

    client = recommender_v1.RecommenderClient()
    recommendations = []

    def _fetch(recommender_id: str, location: str) -> None:
        parent = (
            f"projects/{project_id}/locations/{location}"
            f"/recommenders/{recommender_id}"
        )
        try:
            for rec in client.list_recommendations(parent=parent):
                if rec.state_info.state != recommender_v1.RecommendationStateInfo.State.ACTIVE:
                    continue
                savings = None
                impact = rec.primary_impact
                if impact.category == recommender_v1.Impact.Category.COST:
                    cost = impact.cost_projection.cost
                    savings = {
                        "units": cost.units,
                        "nanos": cost.nanos,
                        "currency_code": cost.currency_code,
                    }
                # Extract recommended action details when present
                actions = []
                for op_group in rec.content.operation_groups:
                    for op in op_group.operations:
                        actions.append({
                            "action": op.action,
                            "resource": op.resource,
                            "path": op.path,
                            "value": str(op.value) if op.value else None,
                        })
                recommendations.append({
                    "recommender": recommender_id,
                    "location": location,
                    "name": rec.name,
                    "description": rec.description,
                    "subtype": rec.recommender_subtype,
                    "estimated_monthly_savings": savings,
                    "actions": actions,
                })
        except Exception as e:  # noqa: BLE001 — surface API errors as data, not exceptions
            recommendations.append({
                "recommender": recommender_id,
                "location": location,
                "error": str(e),
            })

    for location in locations:
        # Heuristic: zones contain at least 2 dashes and end in a letter (us-central1-a)
        is_zone = location[-1].isalpha() and location.count("-") >= 2
        targets = _ZONAL_RECOMMENDERS if is_zone else _REGIONAL_RECOMMENDERS
        for recommender_id in targets:
            _fetch(recommender_id, location)

    total_savings_usd = sum(
        r["estimated_monthly_savings"]["units"]
        for r in recommendations
        if r.get("estimated_monthly_savings") and r["estimated_monthly_savings"].get("units", 0) < 0
    )

    return {
        "project_id": project_id,
        "locations_queried": locations,
        "total_active_recommendations": len([r for r in recommendations if "error" not in r]),
        "estimated_total_monthly_savings_usd": abs(total_savings_usd),
        "recommendations": recommendations,
    }
