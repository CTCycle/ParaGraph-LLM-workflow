from __future__ import annotations

TRAINING_QUERIES = {
    "latest_processing_run": "SELECT * FROM processing_runs ORDER BY executed_at DESC LIMIT 1",
    "latest_checkpoint": "SELECT * FROM checkpoints ORDER BY created_at DESC LIMIT 1",
}
