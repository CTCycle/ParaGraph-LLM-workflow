from __future__ import annotations

from server.services.workflow.provider.models import ModelMetadata, ProviderMetadata


###############################################################################
PROVIDER_REGISTRY: tuple[ProviderMetadata, ...] = (
    ProviderMetadata(
        name="ollama",
        label="Ollama",
        configuration_kind="local",
        model_source="live",
        default_base_url="http://127.0.0.1:11434",
        default_chat_model="llama3.2",
        default_embedding_model="nomic-embed-text",
        requires_api_key=False,
        supports_status_check=True,
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
        supports_tool_selection=True,
    ),
    ProviderMetadata(
        name="openai",
        label="OpenAI",
        configuration_kind="cloud",
        model_source="hosted_registry",
        default_base_url="https://api.openai.com/v1",
        default_chat_model=None,
        default_embedding_model=None,
        requires_api_key=True,
        supports_status_check=False,
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
        supports_tool_selection=True,
        curated_models=(
            ModelMetadata(
                provider="openai",
                model="gpt-5.4",
                label="GPT-5.4",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="openai",
                model="gpt-5-mini",
                label="GPT-5 mini",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="openai",
                model="gpt-5-nano",
                label="GPT-5 nano",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="openai",
                model="gpt-4.1",
                label="GPT-4.1",
                supports_image=True,
            ),
            ModelMetadata(
                provider="openai",
                model="text-embedding-3-small",
                label="Text Embedding 3 Small",
                supports_embeddings=True,
            ),
            ModelMetadata(
                provider="openai",
                model="text-embedding-3-large",
                label="Text Embedding 3 Large",
                supports_embeddings=True,
            ),
        ),
    ),
    ProviderMetadata(
        name="gemini",
        label="Google Gemini",
        configuration_kind="cloud",
        model_source="hosted_registry",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        default_chat_model=None,
        default_embedding_model=None,
        requires_api_key=True,
        supports_status_check=False,
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
        supports_tool_selection=True,
        curated_models=(
            ModelMetadata(
                provider="gemini",
                model="gemini-3-pro-preview",
                label="Gemini 3 Pro Preview",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="gemini",
                model="gemini-3-flash-preview",
                label="Gemini 3 Flash Preview",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="gemini",
                model="gemini-2.5-pro",
                label="Gemini 2.5 Pro",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="gemini",
                model="gemini-2.5-flash",
                label="Gemini 2.5 Flash",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="gemini",
                model="gemini-2.5-flash-lite",
                label="Gemini 2.5 Flash-Lite",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="gemini",
                model="gemini-embedding-001",
                label="Gemini Embedding 001",
                supports_embeddings=True,
            ),
        ),
    ),
    ProviderMetadata(
        name="claude",
        label="Anthropic Claude",
        configuration_kind="cloud",
        model_source="hosted_registry",
        default_base_url="https://api.anthropic.com/v1",
        default_chat_model=None,
        default_embedding_model=None,
        requires_api_key=True,
        supports_status_check=False,
        supports_chat=True,
        supports_embeddings=False,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
        supports_tool_selection=True,
        curated_models=(
            ModelMetadata(
                provider="claude",
                model="claude-opus-4-8",
                label="Claude Opus 4.8",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="claude",
                model="claude-sonnet-4-6",
                label="Claude Sonnet 4.6",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="claude",
                model="claude-haiku-4-5",
                label="Claude Haiku 4.5",
                supports_image=True,
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="claude",
                model="claude-fable-5",
                label="Claude Fable 5",
                supports_image=True,
                supports_reasoning=True,
            ),
        ),
    ),
    ProviderMetadata(
        name="deepseek",
        label="DeepSeek",
        configuration_kind="cloud",
        model_source="hosted_registry",
        default_base_url="https://api.deepseek.com",
        default_chat_model=None,
        default_embedding_model=None,
        requires_api_key=True,
        supports_status_check=False,
        supports_chat=True,
        supports_embeddings=False,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
        supports_tool_selection=True,
        curated_models=(
            ModelMetadata(
                provider="deepseek",
                model="deepseek-v4-pro",
                label="DeepSeek V4 Pro",
                supports_reasoning=True,
            ),
            ModelMetadata(
                provider="deepseek",
                model="deepseek-v4-flash",
                label="DeepSeek V4 Flash",
                supports_reasoning=True,
            ),
        ),
    ),
    ProviderMetadata(
        name="huggingface",
        label="Hugging Face",
        configuration_kind="remote",
        model_source="downloaded_filesystem",
        default_base_url=None,
        default_chat_model=None,
        default_embedding_model=None,
        requires_api_key=True,
        supports_status_check=False,
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=False,
        supports_tool_calling=False,
        supports_tool_selection=True,
    ),
    ProviderMetadata(
        name="lmstudio",
        label="LM Studio",
        configuration_kind="local",
        model_source="live",
        default_base_url="http://localhost:1234/v1",
        default_chat_model="local-model",
        default_embedding_model="local-embedding-model",
        requires_api_key=False,
        supports_status_check=True,
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
        supports_tool_selection=True,
    ),
    ProviderMetadata(
        name="llama",
        label="llama.cpp",
        configuration_kind="local",
        model_source="live",
        default_base_url="http://localhost:8080/v1",
        default_chat_model="local-model",
        default_embedding_model="local-embedding-model",
        requires_api_key=False,
        supports_status_check=True,
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
        supports_tool_selection=True,
    ),
)

PROVIDER_REGISTRY_BY_ID = {item.name: item for item in PROVIDER_REGISTRY}


###############################################################################
def provider_registry_entries() -> tuple[ProviderMetadata, ...]:
    return PROVIDER_REGISTRY


###############################################################################
def provider_registry_entry(provider: str) -> ProviderMetadata:
    normalized = provider.strip().lower()
    try:
        return PROVIDER_REGISTRY_BY_ID[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported provider: {provider}") from exc


###############################################################################
def _normalize_provider(provider: str) -> str:
    return provider.lower().strip()


###############################################################################
def _infer_ollama_metadata(model_name: str) -> ModelMetadata:
    normalized = model_name.lower()
    supports_image = any(
        token in normalized for token in ("llava", "vision", "bakllava", "moondream")
    )
    supports_reasoning = any(
        token in normalized for token in ("deepseek-r1", "qwq", "reason", "qwen3")
    )
    return ModelMetadata(
        provider="ollama",
        model=model_name,
        label=model_name,
        supports_image=supports_image,
        supports_reasoning=supports_reasoning,
        supports_structured_output=True,
    )


###############################################################################
def _infer_huggingface_metadata(repo_id: str) -> ModelMetadata:
    normalized = repo_id.lower()
    supports_image = any(
        token in normalized
        for token in ("vision", "vl", "llava", "pixtral", "moondream")
    )
    supports_reasoning = any(
        token in normalized for token in ("reason", "r1", "r2", "qwq", "o1", "o3")
    )
    return ModelMetadata(
        provider="huggingface",
        model=repo_id,
        label=repo_id,
        supports_image=supports_image,
        supports_reasoning=supports_reasoning,
        supports_structured_output=True,
    )


###############################################################################
def _infer_openai_compatible_local_metadata(
    provider: str, model_name: str
) -> ModelMetadata:
    normalized = model_name.lower()
    supports_image = any(
        token in normalized for token in ("vision", "vl", "llava", "pixtral", "gemma3")
    )
    supports_reasoning = any(
        token in normalized
        for token in ("deepseek", "reason", "r1", "qwq", "qwen3", "gpt-oss")
    )
    supports_embeddings = any(token in normalized for token in ("embed", "bge", "e5"))
    return ModelMetadata(
        provider=provider,
        model=model_name,
        label=model_name,
        supports_image=supports_image,
        supports_embeddings=supports_embeddings,
        supports_reasoning=supports_reasoning,
        supports_structured_output=True,
    )
