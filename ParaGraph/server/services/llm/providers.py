from __future__ import annotations

import os
from enum import Enum
from typing import Any, Protocol

import httpx


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
    ANTHROPIC = "anthropic"


# -----------------------------------------------------------------------------
def _get_timeout(timeout_s: float | None) -> float:
    if timeout_s is not None:
        return timeout_s
    try:
        return float(os.getenv("LLM_TIMEOUT_S", "30"))
    except ValueError:
        return 30.0


# -----------------------------------------------------------------------------
def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
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


###############################################################################
class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout_s: float | None = None) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
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
            "messages": messages,
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
        self.provider = CloudProvider(provider.lower())
        self.timeout = _get_timeout(timeout_s)

        default_base_url = {
            CloudProvider.OPENAI: os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1",
            CloudProvider.GEMINI: os.getenv("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta",
            CloudProvider.ANTHROPIC: "https://api.anthropic.com/v1",
        }
        default_api_key = {
            CloudProvider.OPENAI: os.getenv("OPENAI_API_KEY"),
            CloudProvider.GEMINI: os.getenv("GEMINI_API_KEY"),
            CloudProvider.ANTHROPIC: os.getenv("ANTHROPIC_API_KEY"),
        }

        self.base_url = (base_url or default_base_url[self.provider]).rstrip("/")
        self.api_key = api_key or default_api_key[self.provider]

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
            raise LLMError(
                f"{self.provider.value} request failed ({response.status_code}): {response.text}"
            )

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
            raise LLMError("OpenAI provider is not configured. Set OPENAI_API_KEY.")

        payload: dict[str, Any] = {"model": model, "messages": messages}
        if options:
            payload.update(options)
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
        options: dict[str, Any] | None,
    ) -> str:
        if not self.api_key:
            raise LLMError("Gemini provider is not configured. Set GEMINI_API_KEY.")

        contents: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user")).lower()
            gemini_role = "model" if role in {"assistant", "model"} else "user"
            text = _flatten_content(message.get("content", ""))
            if text:
                contents.append({"role": gemini_role, "parts": [{"text": text}]})

        generation_config: dict[str, Any] = {}
        if options:
            if "temperature" in options:
                generation_config["temperature"] = options["temperature"]
            if "max_output_tokens" in options:
                generation_config["maxOutputTokens"] = options["max_output_tokens"]

        payload: dict[str, Any] = {"contents": contents}
        if generation_config:
            payload["generationConfig"] = generation_config

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
            if format == "json":
                raise LLMError("Gemini JSON mode is not implemented in this MVP.")
            return self._chat_gemini(model=model, messages=messages, options=options)

        raise LLMError("Anthropic provider is visible but not configured in this MVP.")


# -----------------------------------------------------------------------------
def select_llm_provider(provider: str, **kwargs: Any) -> SupportsChat:
    normalized = provider.strip().lower()
    if normalized in {"ollama", "local"}:
        return OllamaClient(
            base_url=kwargs.get("base_url"),
            timeout_s=kwargs.get("timeout_s"),
        )

    if normalized in {CloudProvider.OPENAI.value, CloudProvider.GEMINI.value, CloudProvider.ANTHROPIC.value}:
        return CloudLLMClient(
            provider=normalized,
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            timeout_s=kwargs.get("timeout_s"),
        )

    raise LLMError(f"Unsupported provider: {provider}")
