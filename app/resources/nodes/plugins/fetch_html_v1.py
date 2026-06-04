from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup
import httpx

from server.services.workflow.node_handlers.common import (
    coerce_bool,
    coerce_float,
    coerce_text,
)


def _as_object(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
    return {str(key): coerce_text(value) for key, value in headers.items()}


def _extract_text(html: str, *, strip_scripts_and_styles: bool) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if strip_scripts_and_styles:
        for tag in soup(["script", "style"]):
            tag.decompose()
    return "\n".join(
        part.strip() for part in soup.get_text("\n").splitlines() if part.strip()
    )


def _extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title is None:
        return None
    title = coerce_text(soup.title.get_text()).strip()
    return title or None


def execute(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    url = coerce_text(
        inputs.get("url")
        if "url" in inputs and inputs.get("url") is not None
        else parameters.get("url")
    ).strip()
    if not url:
        raise ValueError("url is required")

    timeout_s = max(0.1, coerce_float(parameters.get("timeout_s"), 15.0))
    follow_redirects = coerce_bool(parameters.get("follow_redirects", True))
    headers = _normalize_headers(_as_object(parameters.get("headers"), label="headers"))
    strip_scripts_and_styles = coerce_bool(
        parameters.get("strip_scripts_and_styles", True)
    )
    extract_text = coerce_bool(parameters.get("extract_text", True))

    with httpx.Client(timeout=timeout_s, follow_redirects=follow_redirects) as client:
        response = client.get(url, headers=headers)

    raw_html = response.text
    cleaned_text = (
        _extract_text(raw_html, strip_scripts_and_styles=strip_scripts_and_styles)
        if extract_text
        else ""
    )
    content_type = response.headers.get("content-type") or ""

    response_payload: dict[str, Any] = {
        "status_code": response.status_code,
        "final_url": str(response.url),
        "headers": dict(response.headers),
        "elapsed_ms": round(response.elapsed.total_seconds() * 1000.0, 3),
        "content_type": content_type,
    }
    title = _extract_title(raw_html)
    if title is not None:
        response_payload["title"] = title

    return {"html": raw_html, "text": cleaned_text, "response": response_payload}
