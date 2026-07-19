from __future__ import annotations

import base64
import email.utils
import ipaddress
import json
import random
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx

from server.common import path as common_path
from server.common.security import ensure_path_within_root
from server.domain.node_handler_http import HttpRequestParameters
from server.services.configuration import configuration_service


SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "idempotency-key",
}
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
RETRYABLE_METHODS = {"GET", "PUT", "DELETE", "HEAD", "OPTIONS"}

###############################################################################
class HttpTransportError(ValueError):

    # -------------------------------------------------------------------------
    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.code = code
        self.details = details
        super().__init__(message)

###############################################################################
class SecureHttpTransport:

    # -------------------------------------------------------------------------
    def __init__(
        self,
        *,
        resolver: Callable[[str, int], list[str]] | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._resolver = resolver or self._resolve_addresses
        self._transport = transport
        self._sleep = sleep
        self._jitter = jitter
        self._cancelled = cancelled or (lambda: False)

    # -------------------------------------------------------------------------
    @staticmethod
    def _resolve_addresses(host: str, port: int) -> list[str]:
        return sorted(
            {
                str(result[4][0])
                for result in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            }
        )

    # -------------------------------------------------------------------------
    @staticmethod
    def _validate_address(address: str) -> None:
        parsed = ipaddress.ip_address(address)
        if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
            parsed = parsed.ipv4_mapped
        if (
            parsed.is_loopback
            or parsed.is_private
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_unspecified
            or parsed.is_reserved
        ):
            raise HttpTransportError(
                "ssrf_blocked",
                "HTTP request target resolved to a blocked network address",
            )

    # -------------------------------------------------------------------------
    def _validate_and_pin(self, url: str) -> tuple[str, str, tuple[str, str, int]]:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise HttpTransportError(
                "invalid_url", "HTTP request URL must use http or https"
            )
        if parsed.username or parsed.password:
            raise HttpTransportError(
                "credential_url", "Credential-bearing URLs are forbidden"
            )
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = self._resolver(parsed.hostname, port)
        if not addresses:
            raise HttpTransportError("dns_resolution_failed", "Hostname resolved to no addresses")
        for address in addresses:
            self._validate_address(address)
        pinned_address = addresses[0]
        pinned_host = f"[{pinned_address}]" if ":" in pinned_address else pinned_address
        default_port = 443 if parsed.scheme == "https" else 80
        netloc = pinned_host if port == default_port else f"{pinned_host}:{port}"
        pinned_url = urlunsplit(
            (parsed.scheme, netloc, parsed.path or "/", parsed.query, parsed.fragment)
        )
        return pinned_url, parsed.hostname, (parsed.scheme, parsed.hostname.lower(), port)

    # -------------------------------------------------------------------------
    @staticmethod
    def _accepted(status: int, accepted: list[int | str]) -> bool:
        for item in accepted:
            if isinstance(item, int) and status == item:
                return True
            text = str(item).strip()
            if text.isdigit() and status == int(text):
                return True
            if "-" in text:
                start, _, end = text.partition("-")
                if start.isdigit() and end.isdigit() and int(start) <= status <= int(end):
                    return True
        return False

    # -------------------------------------------------------------------------
    @staticmethod
    def _retry_after(value: str | None) -> float | None:
        if not value:
            return None
        stripped = value.strip()
        if stripped.isdigit():
            return float(stripped)
        try:
            parsed = email.utils.parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0.0, (parsed - datetime.now(UTC)).total_seconds())

    # -------------------------------------------------------------------------
    @staticmethod
    def _redact_headers(headers: httpx.Headers | dict[str, str]) -> dict[str, str]:
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_HEADERS else str(value)
            for key, value in headers.items()
        }

    # -------------------------------------------------------------------------
    @staticmethod
    def _resolve_artifact_path(path_value: str) -> Path:
        candidate = Path(path_value).expanduser()
        if not candidate.is_absolute():
            candidate = common_path.ARTIFACT_ROOT / candidate
        return ensure_path_within_root(
            candidate.resolve(), common_path.ARTIFACT_ROOT.resolve(), label="artifact path"
        )

    # -------------------------------------------------------------------------
    @staticmethod
    def _resolve_credentials(parameters: HttpRequestParameters) -> tuple[str, str | None]:
        if parameters.auth_mode == "none":
            return "", None
        profile = configuration_service.load_configuration_profile(
            session_name=None, profile_name=parameters.credential_profile
        )
        access_key = next(
            (
                item
                for item in profile.access_keys
                if item.provider == parameters.credential_provider.strip().lower()
            ),
            None,
        )
        if access_key is None or not access_key.api_key:
            raise HttpTransportError(
                "credential_unavailable",
                "Credential profile does not contain the requested HTTP credential",
            )
        return access_key.api_key, access_key.base_url

    # -------------------------------------------------------------------------
    def _request_content(
        self, parameters: HttpRequestParameters, inputs: dict[str, Any]
    ) -> tuple[dict[str, Any], list[Any]]:
        body = inputs.get("body")
        opened: list[Any] = []
        if parameters.body_mode == "none":
            return {}, opened
        if parameters.body_mode == "json":
            return {"json": body if body is not None else parameters.json_body}, opened
        if parameters.body_mode == "text":
            return {"content": str(body if body is not None else parameters.text_body)}, opened
        if parameters.body_mode == "form":
            return {"data": body if isinstance(body, dict) else parameters.form_body}, opened
        if parameters.body_mode == "binary":
            raw = body if body is not None else parameters.text_body
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            if not isinstance(raw, bytes):
                raise HttpTransportError("invalid_body", "Binary body must be bytes or text")
            return {"content": raw}, opened
        if parameters.body_mode == "file":
            path = self._resolve_artifact_path(parameters.upload_path)
            handle = path.open("rb")
            opened.append(handle)
            return {"content": handle}, opened
        fields = dict(parameters.multipart_fields)
        files: dict[str, Any] = {}
        if parameters.upload_path:
            path = self._resolve_artifact_path(parameters.upload_path)
            handle = path.open("rb")
            opened.append(handle)
            files["file"] = (path.name, handle)
        return {"data": fields, "files": files}, opened

    # -------------------------------------------------------------------------
    def execute(
        self, parameters: HttpRequestParameters, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        started = time.monotonic()
        secret, profile_base_url = self._resolve_credentials(parameters)
        initial_url = str(inputs.get("url") or parameters.url or profile_base_url or "").strip()
        if not initial_url:
            raise HttpTransportError("invalid_url", "HTTP request URL is required")
        headers = {str(key): str(value) for key, value in parameters.headers.items()}
        if parameters.idempotency_key:
            headers["Idempotency-Key"] = parameters.idempotency_key
        auth: httpx.Auth | None = None
        if parameters.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {secret}"
        elif parameters.auth_mode == "api_key":
            headers[parameters.api_key_header] = secret
        elif parameters.auth_mode == "basic":
            auth = httpx.BasicAuth(parameters.username, secret)

        body_kwargs, opened = self._request_content(parameters, inputs)
        attempts: list[dict[str, Any]] = []
        partial_path: Path | None = None
        try:
            timeout = httpx.Timeout(
                connect=parameters.connect_timeout,
                read=parameters.read_timeout,
                write=parameters.write_timeout,
                pool=parameters.pool_timeout,
            )
            with httpx.Client(
                timeout=timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                for attempt in range(1, parameters.max_attempts + 1):
                    if self._cancelled():
                        raise HttpTransportError("cancelled", "HTTP request was cancelled")
                    if time.monotonic() - started >= parameters.overall_timeout:
                        raise HttpTransportError("overall_timeout", "HTTP overall timeout elapsed")
                    current_url = initial_url
                    current_headers = dict(headers)
                    redirects = 0
                    try:
                        while True:
                            pinned_url, original_host, origin = self._validate_and_pin(current_url)
                            default_port = 443 if origin[0] == "https" else 80
                            current_headers["Host"] = (
                                original_host
                                if origin[2] == default_port
                                else f"{original_host}:{origin[2]}"
                            )
                            extensions = {"sni_hostname": original_host.encode("ascii")}
                            with client.stream(
                                parameters.method,
                                pinned_url,
                                params=parameters.query,
                                headers=current_headers,
                                auth=auth,
                                extensions=extensions,
                                **body_kwargs,
                            ) as response:
                                location = response.headers.get("location")
                                if response.status_code in REDIRECT_STATUSES and location:
                                    if redirects >= parameters.max_redirects:
                                        raise HttpTransportError(
                                            "redirect_limit", "HTTP redirect limit exceeded"
                                        )
                                    target = urljoin(current_url, location)
                                    target_parts = urlsplit(target)
                                    if (
                                        urlsplit(current_url).scheme == "https"
                                        and target_parts.scheme == "http"
                                        and not parameters.allow_https_downgrade
                                    ):
                                        raise HttpTransportError(
                                            "redirect_downgrade",
                                            "HTTPS to HTTP redirect is forbidden",
                                        )
                                    _, _, target_origin = self._validate_and_pin(target)
                                    if target_origin != origin:
                                        current_headers = {
                                            key: value
                                            for key, value in current_headers.items()
                                            if key.lower()
                                            not in {
                                                "authorization",
                                                "cookie",
                                                "proxy-authorization",
                                                "x-api-key",
                                                "idempotency-key",
                                            }
                                        }
                                        auth = None
                                    current_url = target
                                    redirects += 1
                                    continue

                                limit = (
                                    parameters.max_download_bytes
                                    if parameters.response_mode == "file"
                                    else parameters.max_response_bytes
                                )
                                chunks: list[bytes] = []
                                byte_count = 0
                                output_handle = None
                                final_path = None
                                if parameters.response_mode == "file":
                                    final_path = self._resolve_artifact_path(parameters.download_path)
                                    final_path.parent.mkdir(parents=True, exist_ok=True)
                                    partial_path = final_path.with_name(
                                        f".{final_path.name}.partial-{uuid4().hex}"
                                    )
                                    output_handle = partial_path.open("wb")
                                try:
                                    for chunk in response.iter_bytes():
                                        byte_count += len(chunk)
                                        if byte_count > limit:
                                            raise HttpTransportError(
                                                "response_too_large",
                                                "HTTP response exceeded the configured size limit",
                                                limit=limit,
                                            )
                                        if output_handle:
                                            output_handle.write(chunk)
                                        else:
                                            chunks.append(chunk)
                                        if (
                                            time.monotonic() - started
                                            >= parameters.overall_timeout
                                        ):
                                            raise HttpTransportError(
                                                "overall_timeout",
                                                "HTTP overall timeout elapsed",
                                            )
                                finally:
                                    if output_handle:
                                        output_handle.close()
                                content = b"".join(chunks)
                                accepted = self._accepted(
                                    response.status_code, parameters.accepted_statuses
                                )
                                attempt_meta = {
                                    "attempt": attempt,
                                    "status_code": response.status_code,
                                    "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                                }
                                attempts.append(attempt_meta)
                                if not accepted:
                                    excerpt = content[:512].decode("utf-8", errors="replace")
                                    if secret:
                                        excerpt = excerpt.replace(secret, "[REDACTED]")
                                    if (
                                        response.status_code in parameters.retry_statuses
                                        and attempt < parameters.max_attempts
                                    ):
                                        delay = self._retry_after(response.headers.get("retry-after"))
                                        if delay is None:
                                            delay = parameters.backoff_seconds * (2 ** (attempt - 1))
                                            delay += delay * 0.25 * self._jitter()
                                        delay = min(delay, parameters.max_retry_delay)
                                        attempts[-1]["retry_delay_seconds"] = delay
                                        attempts[-1]["retry_reason"] = f"HTTP {response.status_code}"
                                        if partial_path:
                                            partial_path.unlink(missing_ok=True)
                                            partial_path = None
                                        self._sleep(delay)
                                        break
                                    raise HttpTransportError(
                                        "http_status",
                                        f"HTTP response status {response.status_code} was not accepted",
                                        status_code=response.status_code,
                                        excerpt=excerpt,
                                        attempts=attempts,
                                    )

                                if partial_path and final_path:
                                    partial_path.replace(final_path)
                                    partial_path = None

                                text = content.decode("utf-8", errors="replace")
                                json_value: Any = None
                                if parameters.response_mode in {"auto", "json"}:
                                    try:
                                        json_value = json.loads(text)
                                    except ValueError as exc:
                                        if parameters.response_mode == "json":
                                            raise HttpTransportError(
                                                "invalid_json", "HTTP response was not valid JSON"
                                            ) from exc
                                return {
                                    "ok": True,
                                    "status_code": response.status_code,
                                    "headers": self._redact_headers(response.headers),
                                    "final_url": current_url,
                                    "text": text if parameters.response_mode != "binary" else "",
                                    "json": json_value,
                                    "binary_base64": (
                                        base64.b64encode(content).decode("ascii")
                                        if parameters.response_mode == "binary"
                                        else ""
                                    ),
                                    "download_path": (
                                        str(final_path) if parameters.response_mode == "file" else ""
                                    ),
                                    "byte_count": byte_count,
                                    "attempts": attempts,
                                    "redirect_count": redirects,
                                }
                    except (httpx.TimeoutException, httpx.TransportError) as exc:
                        attempts.append(
                            {"attempt": attempt, "retry_reason": type(exc).__name__}
                        )
                        safe_retry = parameters.method in RETRYABLE_METHODS or bool(
                            parameters.idempotency_key or parameters.retry_unsafe
                        )
                        if attempt >= parameters.max_attempts or not safe_retry:
                            raise HttpTransportError(
                                "transport_error",
                                "HTTP transport failed",
                                attempts=attempts,
                            ) from exc
                        delay = min(
                            parameters.backoff_seconds * (2 ** (attempt - 1)),
                            parameters.max_retry_delay,
                        )
                        attempts[-1]["retry_delay_seconds"] = delay
                        self._sleep(delay)
        finally:
            for handle in opened:
                handle.close()
            if partial_path:
                partial_path.unlink(missing_ok=True)

        raise HttpTransportError("retry_exhausted", "HTTP retry policy was exhausted")
