from __future__ import annotations

DATASET_QUERIES = {
    "list_datasets": "SELECT * FROM datasets ORDER BY created_at DESC",
    "count_datasets": "SELECT COUNT(*) AS total FROM datasets",
}
