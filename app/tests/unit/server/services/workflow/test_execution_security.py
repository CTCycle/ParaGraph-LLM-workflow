from __future__ import annotations

from server.services.workflow.execution import execution_service


###############################################################################
def test_redact_output_state_masks_sensitive_controller_fields() -> None:
    output_state = {
        "inputs": {"prompt": "hello"},
        "controllers": {
            "connection": {
                "engine": "postgresql",
                "username": "analyst",
                "password": "super-secret",
                "api_key": "token-value",
            }
        },
        "ports": {"result": "ok"},
    }

    redacted = execution_service._redact_output_state(output_state)  # noqa: SLF001

    assert redacted["controllers"]["connection"]["password"] == "***"
    assert redacted["controllers"]["connection"]["api_key"] == "***"
    assert redacted["controllers"]["connection"]["username"] == "analyst"
