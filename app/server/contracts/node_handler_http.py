from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

###############################################################################
class HttpRequestParameters(BaseModel):
    url: str = ""
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, Any] = Field(default_factory=dict)
    body_mode: Literal["none", "json", "text", "form", "multipart", "binary", "file"] = "none"
    json_body: Any = None
    text_body: str = ""
    form_body: dict[str, Any] = Field(default_factory=dict)
    multipart_fields: dict[str, Any] = Field(default_factory=dict)
    upload_path: str = ""
    response_mode: Literal["auto", "json", "text", "binary", "file"] = "auto"
    download_path: str = ""
    accepted_statuses: list[int | str] = Field(default_factory=lambda: ["200-299"])
    credential_profile: str = ""
    credential_provider: str = "http"
    auth_mode: Literal["none", "bearer", "api_key", "basic"] = "none"
    api_key_header: str = "X-API-Key"
    username: str = ""
    connect_timeout: float = Field(default=10.0, gt=0, le=120)
    read_timeout: float = Field(default=30.0, gt=0, le=600)
    write_timeout: float = Field(default=30.0, gt=0, le=600)
    pool_timeout: float = Field(default=10.0, gt=0, le=120)
    overall_timeout: float = Field(default=60.0, gt=0, le=1800)
    max_response_bytes: int = Field(default=2_000_000, gt=0, le=50_000_000)
    max_download_bytes: int = Field(default=100_000_000, gt=0, le=1_000_000_000)
    max_redirects: int = Field(default=0, ge=0, le=10)
    allow_https_downgrade: bool = False
    max_attempts: int = Field(default=1, ge=1, le=10)
    backoff_seconds: float = Field(default=0.25, ge=0, le=60)
    max_retry_delay: float = Field(default=60.0, ge=0, le=600)
    retry_statuses: list[int] = Field(default_factory=lambda: [429, 502, 503, 504])
    retry_unsafe: bool = False
    idempotency_key: str = ""

    # -------------------------------------------------------------------------
    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, value: Any) -> str:
        return str(value or "GET").strip().upper()

    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_modes(self) -> "HttpRequestParameters":
        if self.body_mode == "file" and not self.upload_path.strip():
            raise ValueError("file body mode requires upload_path")
        if self.response_mode == "file" and not self.download_path.strip():
            raise ValueError("file response mode requires download_path")
        if self.auth_mode != "none" and not self.credential_profile.strip():
            raise ValueError("authenticated HTTP requests require credential_profile")
        if self.max_attempts > 1 and self.method in {"POST", "PATCH"}:
            if not self.idempotency_key.strip() and not self.retry_unsafe:
                raise ValueError(
                    "unsafe HTTP retries require idempotency_key or retry_unsafe"
                )
        return self


class HttpGetParameters(HttpRequestParameters):
    method: Literal["GET"] = "GET"
    body_mode: Literal["none"] = "none"


class HttpPostParameters(HttpRequestParameters):
    method: Literal["POST"] = "POST"


class HttpPutParameters(HttpRequestParameters):
    method: Literal["PUT"] = "PUT"


class HttpPatchParameters(HttpRequestParameters):
    method: Literal["PATCH"] = "PATCH"


class HttpDeleteParameters(HttpRequestParameters):
    method: Literal["DELETE"] = "DELETE"
    body_mode: Literal["none"] = "none"
