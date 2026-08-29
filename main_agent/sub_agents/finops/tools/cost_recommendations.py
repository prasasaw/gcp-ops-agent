"""Phase 1: idle/unused resource cost recommendations via the GCP Recommender API."""

import os
from typing import Optional

from google.cloud import recommender_v1

# Recommenders that require a zone/region location, mapped to their default fallback.
# Callers should pass explicit locations for accurate zone-level results.
_ZONAL_RECOMMENDERS = [
    "google.compute.instance.IdleResourceRecommender",
    "google.compute.disk.IdleResourceRecommender",
]
_REGIONAL_RECOMMENDERS = [
    "google.cloudsql.instance.IdleRecommender",
]
_GLOBAL_RECOMMENDERS = [
    "google.compute.address.IdleResourceRecommender",
]


def get_cost_recommendations(
    project_id: Optional[str] = None,
    locations: Optional[list[str]] = None,
) -> dict:
    """Return active idle-resource cost recommendations for a GCP project.

    locations: explicit list of zones/regions (e.g. ['us-central1-a', 'us-central1']).
    Falls back to RECOMMENDER_LOCATIONS env var (comma-separated) or skips zonal recommenders.
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
                recommendations.append({
                    "recommender": recommender_id,
                    "location": location,
                    "name": rec.name,
                    "description": rec.description,
                    "subtype": rec.recommender_subtype,
                    "estimated_monthly_savings": savings,
                })
        except Exception as e:  # noqa: BLE001 — surface API errors as data, not exceptions
            recommendations.append({
                "recommender": recommender_id,
                "location": location,
                "error": str(e),
            })

    for recommender_id in _GLOBAL_RECOMMENDERS:
        _fetch(recommender_id, "global")

    for location in locations:
        # Heuristic: zones contain a digit (us-central1-a), regions do not (us-central1)
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
        "locations_queried": ["global"] + locations,
        "total_active_recommendations": len([r for r in recommendations if "error" not in r]),
        "estimated_total_monthly_savings_usd": abs(total_savings_usd),
        "recommendations": recommendations,
    }
