from __future__ import annotations

import base64
import mimetypes
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import httpx

from ParaGraph.server.configurations.startup import get_llm_timeout_seconds

###############################################################################
class OllamaError(RuntimeError):
    pass


###############################################################################
class OllamaTimeout(OllamaError):
    pass


###############################################################################
class LLMError(RuntimeError):
    pass


###############################################################################
class LLMTimeout(LLMError):
    pass


###############################################################################
class SupportsChat(Protocol):
    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str: ...


###############################################################################
class CloudProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"


# -----------------------------------------------------------------------------
def _get_timeout(timeout_s: float | None) -> float:
    if timeout_s is not None:
        return timeout_s
    return get_llm_timeout_seconds()


# -----------------------------------------------------------------------------
def _normalize_provider_name(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "anthropic":
        return "claude"
    return normalized


# -----------------------------------------------------------------------------
def _read_image_payload(path_value: str) -> dict[str, str]:
    image_path = Path(path_value)
    if not image_path.exists() or not image_path.is_file():
        raise LLMError(f"Image not found: {path_value}")

    mime_type, _ = mimetypes.guess_type(str(image_path))
    media_type = mime_type or "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return {
        "mime_type": media_type,
        "data": encoded,
        "data_url": f"data:{media_type};base64,{encoded}",
    }


# -----------------------------------------------------------------------------
def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(part for part in parts if part)
    return str(content)


# -----------------------------------------------------------------------------
def messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role", "user")).upper()
        content = _flatten_content(message.get("content", ""))
        if content:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


# -----------------------------------------------------------------------------
def _content_blocks(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        blocks = [item for item in value if isinstance(item, dict)]
        if blocks:
            return blocks
    text = _flatten_content(value)
    if not text:
        return []
    return [{"type": "text", "text": text}]


# -----------------------------------------------------------------------------
def _to_openai_content(value: Any) -> str | list[dict[str, Any]]:
    blocks = _content_blocks(value)
    if not blocks:
        return ""
    if len(blocks) == 1 and blocks[0].get("type") == "text":
        return str(blocks[0].get("text", ""))

    content: list[dict[str, Any]] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "text":
            content.append({"type": "text", "text": str(block.get("text", ""))})
        elif block_type == "image_path":
            image = _read_image_payload(str(block.get("path", "")))
            content.append({"type": "image_url", "image_url": {"url": image["data_url"]}})
    return content


# -----------------------------------------------------------------------------
def _to_ollama_message(message: dict[str, Any]) -> dict[str, Any]:
    text_parts: list[str] = []
    images: list[str] = []
    for block in _content_blocks(message.get("content", "")):
        if block.get("type") == "text":
            text_parts.append(str(block.get("text", "")))
        elif block.get("type") == "image_path":
            images.append(_read_image_payload(str(block.get("path", "")))["data"])

    payload = {
        "role": str(message.get("role", "user")),
        "content": "\n".join(part for part in text_parts if part).strip(),
    }
    if images:
        payload["images"] = images
    return payload


# -----------------------------------------------------------------------------
def _to_gemini_parts(value: Any) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for block in _content_blocks(value):
        if block.get("type") == "text":
            text = str(block.get("text", "")).strip()
            if text:
                parts.append({"text": text})
        elif block.get("type") == "image_path":
            image = _read_image_payload(str(block.get("path", "")))
            parts.append(
                {
                    "inline_data": {
                        "mime_type": image["mime_type"],
                        "data": image["data"],
                    }
                }
            )
    return parts


# -----------------------------------------------------------------------------
def _to_claude_blocks(value: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for block in _content_blocks(value):
        if block.get("type") == "text":
            text = str(block.get("text", "")).strip()
            if text:
                blocks.append({"type": "text", "text": text})
        elif block.get("type") == "image_path":
            image = _read_image_payload(str(block.get("path", "")))
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image["mime_type"],
                        "data": image["data"],
                    },
                }
            )
    return blocks


###############################################################################
class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout_s: float | None = None) -> None:
        self.base_url = (base_url or "http://127.0.0.1:11434").rstrip("/")
        self.timeout = _get_timeout(timeout_s)

    # -------------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> httpx.Response:
        try:
            response = httpx.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=payload,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise OllamaTimeout("Ollama request timed out") from exc
        except httpx.RequestError as exc:
            raise OllamaError(f"Unable to reach Ollama: {exc}") from exc

        if allow_404 and response.status_code == 404:
            return response
        if response.is_error:
            raise OllamaError(f"Ollama request failed ({response.status_code}): {response.text}")
        return response

    # -------------------------------------------------------------------------
    def list_models(self) -> list[str]:
        response = self._request("GET", "/api/tags")
        payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names: list[str] = []
        for model in models:
            if isinstance(model, dict) and isinstance(model.get("name"), str):
                names.append(model["name"])
        return names

    # -------------------------------------------------------------------------
    def check_model_availability(self, name: str, auto_pull: bool = True) -> bool:
        if name in self.list_models():
            return True
        if not auto_pull:
            return False
        self._request("POST", "/api/pull", payload={"name": name, "stream": False})
        return name in self.list_models()

    # -------------------------------------------------------------------------
    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [_to_ollama_message(message) for message in messages],
            "stream": False,
        }
        if format:
            payload["format"] = format
        if options:
            payload["options"] = options

        response = self._request("POST", "/api/chat", payload=payload, allow_404=True)
        if response.status_code != 404:
            data = response.json()
            message = data.get("message", {}) if isinstance(data, dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            text = _flatten_content(content)
            if text:
                return text
            raise OllamaError("Invalid /api/chat response shape")

        generate_payload: dict[str, Any] = {
            "model": model,
            "prompt": messages_to_prompt(messages),
            "stream": False,
        }
        images: list[str] = []
        for message in messages:
            transformed = _to_ollama_message(message)
            images.extend(transformed.get("images", []))
        if images:
            generate_payload["images"] = images
        if format:
            generate_payload["format"] = format
        if options:
            generate_payload["options"] = options

        fallback_response = self._request("POST", "/api/generate", payload=generate_payload)
        fallback_data = fallback_response.json()
        generated = fallback_data.get("response") if isinstance(fallback_data, dict) else None
        text = _flatten_content(generated)
        if text:
            return text
        raise OllamaError("Invalid /api/generate response shape")


###############################################################################
class CloudLLMClient:
    def __init__(
        self,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        normalized_provider = _normalize_provider_name(provider)
        self.provider = CloudProvider(normalized_provider)
        self.timeout = _get_timeout(timeout_s)

        default_base_url = {
            CloudProvider.OPENAI: "https://api.openai.com/v1",
            CloudProvider.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
            CloudProvider.CLAUDE: "https://api.anthropic.com/v1",
        }

        self.base_url = (base_url or default_base_url[self.provider]).rstrip("/")
        self.api_key = api_key

    # -------------------------------------------------------------------------
    def _request(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(f"{self.provider.value} request timed out") from exc
        except httpx.RequestError as exc:
            raise LLMError(f"Unable to reach {self.provider.value}: {exc}") from exc

        if response.is_error:
            raise LLMError(f"{self.provider.value} request failed ({response.status_code}): {response.text}")

        data = response.json()
        if not isinstance(data, dict):
            raise LLMError(f"Unexpected {self.provider.value} response payload")
        return data

    # -------------------------------------------------------------------------
    def _chat_openai(
        self,
        model: str,
        messages: list[dict[str, Any]],
        format: str | None,
        options: dict[str, Any] | None,
    ) -> str:
        if not self.api_key:
            raise LLMError("OpenAI provider is not configured. Add an API key in Configurations.")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": str(message.get("role", "user")),
                    "content": _to_openai_content(message.get("content", "")),
                }
                for message in messages
            ],
        }
        if options:
            if "temperature" in options:
                payload["temperature"] = options["temperature"]
            if "top_p" in options:
                payload["top_p"] = options["top_p"]
            if "max_output_tokens" in options:
                payload["max_tokens"] = options["max_output_tokens"]
        if format == "json":
            payload["response_format"] = {"type": "json_object"}

        data = self._request(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        choices = data.get("choices", [])
        if not choices:
            raise LLMError("OpenAI response does not include choices")
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        text = _flatten_content(content)
        if text:
            return text
        raise LLMError("OpenAI response message content is empty")

    # -------------------------------------------------------------------------
    def _chat_gemini(
        self,
        model: str,
        messages: list[dict[str, Any]],
        format: str | None,
        options: dict[str, Any] | None,
    ) -> str:
        if not self.api_key:
            raise LLMError("Gemini provider is not configured. Add an API key in Configurations.")

        contents: list[dict[str, Any]] = []
        system_parts: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user")).lower()
            parts = _to_gemini_parts(message.get("content", ""))
            if not parts:
                continue
            if role == "system":
                system_parts.extend(parts)
                continue
            gemini_role = "model" if role in {"assistant", "model"} else "user"
            contents.append({"role": gemini_role, "parts": parts})

        generation_config: dict[str, Any] = {}
        if options:
            if "temperature" in options:
                generation_config["temperature"] = options["temperature"]
            if "max_output_tokens" in options:
                generation_config["maxOutputTokens"] = options["max_output_tokens"]
        if format == "json":
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {"contents": contents}
        if generation_config:
            payload["generationConfig"] = generation_config
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        data = self._request(
            url=f"{self.base_url}/models/{model}:generateContent",
            payload=payload,
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
        )

        candidates = data.get("candidates", [])
        if not candidates:
            raise LLMError("Gemini response does not include candidates")
        candidate = candidates[0] if isinstance(candidates[0], dict) else {}
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []

        text_parts: list[str] = []
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])

        text = "\n".join(text_parts).strip()
        if text:
            return text
        raise LLMError("Gemini response content is empty")

    # -------------------------------------------------------------------------
    def _chat_claude(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: dict[str, Any] | None,
    ) -> str:
        if not self.api_key:
            raise LLMError("Claude provider is not configured. Add an API key in Configurations.")

        system_texts: list[str] = []
        api_messages: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user")).lower()
            if role == "system":
                text = _flatten_content(message.get("content", "")).strip()
                if text:
                    system_texts.append(text)
                continue
            blocks = _to_claude_blocks(message.get("content", ""))
            if not blocks:
                continue
            api_messages.append({
                "role": "assistant" if role in {"assistant", "model"} else "user",
                "content": blocks,
            })

        max_tokens = 512
        if options and options.get("max_output_tokens"):
            max_tokens = int(options["max_output_tokens"])

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if system_texts:
            payload["system"] = "\n\n".join(system_texts)
        if options and "temperature" in options:
            payload["temperature"] = options["temperature"]

        data = self._request(
            url=f"{self.base_url}/messages",
            payload=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        content = data.get("content", [])
        if not isinstance(content, list):
            raise LLMError("Claude response does not include content")
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
        text = "\n".join(part for part in text_parts if isinstance(part, str)).strip()
        if text:
            return text
        raise LLMError("Claude response content is empty")

    # -------------------------------------------------------------------------
    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        if self.provider == CloudProvider.OPENAI:
            return self._chat_openai(model=model, messages=messages, format=format, options=options)
        if self.provider == CloudProvider.GEMINI:
            return self._chat_gemini(model=model, messages=messages, format=format, options=options)
        if self.provider == CloudProvider.CLAUDE:
            return self._chat_claude(model=model, messages=messages, options=options)
        raise LLMError(f"Unsupported cloud provider: {self.provider.value}")


# -----------------------------------------------------------------------------
def select_llm_provider(provider: str, **kwargs: Any) -> SupportsChat:
    normalized = _normalize_provider_name(provider)
    if normalized in {"ollama", "local"}:
        return OllamaClient(
            base_url=kwargs.get("base_url"),
            timeout_s=kwargs.get("timeout_s"),
        )

    if normalized in {CloudProvider.OPENAI.value, CloudProvider.GEMINI.value, CloudProvider.CLAUDE.value}:
        return CloudLLMClient(
            provider=normalized,
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            timeout_s=kwargs.get("timeout_s"),
        )

    raise LLMError(f"Unsupported provider: {provider}")

