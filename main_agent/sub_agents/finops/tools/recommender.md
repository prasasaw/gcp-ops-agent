# GCP Recommender Tool — Progress Tracker

## Phase 1 — Idle / Unused Resources ✅
| Recommender ID | Location | Question answered |
|---|---|---|
| `google.compute.address.IdleResourceRecommender` | `global` | Which static IPs are unused? |
| `google.compute.instance.IdleResourceRecommender` | per-zone | Which VMs are idle and can be deleted? |
| `google.compute.disk.IdleResourceRecommender` | per-zone | Which persistent disks are unused? |
| `google.cloudsql.instance.IdleRecommender` | per-region | Which Cloud SQL instances are idle? |

**Tool:** `get_cost_recommendations(project_id, locations)`  
**Env var:** `RECOMMENDER_LOCATIONS` (comma-separated zones/regions, e.g. `us-central1-a,us-central1`)  
**Output:** list of active recommendations with description + estimated monthly savings

---

## Phase 2 — Right-sizing ✅
| Recommender ID | Location | Question answered |
|---|---|---|
| `google.compute.instance.MachineTypeRecommender` | per-zone | Which VMs are over/under-provisioned? |
| `google.cloudsql.instance.OverprovisionedRecommender` | per-region | Which Cloud SQL instances are over-provisioned? |
| `google.run.service.CostRecommender` | per-region | Which Cloud Run services should switch CPU allocation? |

**Tool:** `get_rightsizing_recommendations(project_id, locations)`  
**Env var:** `PROJECT_LOCATION` (comma-separated zones/regions)  
**Output:** list of active recommendations with description, estimated monthly savings, and recommended actions

---

## Phase 3 — Commitments & Discounts 🔲
| Recommender ID | Location | Question answered |
|---|---|---|
| `google.cloudbilling.commitment.SpendBasedCommitmentRecommender` | `global` | Should I buy spend-based CUDs? |
| `google.compute.commitment.UsageCommitmentRecommender` | per-region | Should I buy resource-based CUDs? |
| `google.bigquery.capacityCommitments.Recommender` | `global` | Should I buy BigQuery slot commitments? |

---

## Phase 4 — Storage & Misc 🔲
| Recommender ID | Location | Question answered |
|---|---|---|
| `google.bigquery.table.PartitionClusterRecommender` | `global` | Should I partition/cluster my BigQuery tables? |
| `google.storage.bucket.SoftDeleteRecommender` | `global` | Should I enable/disable soft delete on GCS buckets? |
