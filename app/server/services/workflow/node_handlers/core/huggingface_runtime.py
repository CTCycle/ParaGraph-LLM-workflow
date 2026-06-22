from __future__ import annotations

from typing import Any

import torch
import transformers

###############################################################################
def load_huggingface_modules() -> tuple[Any, Any, Any]:
    auto_model_for_causal_lm = getattr(transformers, "AutoModelForCausalLM", None)
    auto_tokenizer = getattr(transformers, "AutoTokenizer", None)
    if auto_model_for_causal_lm is None or auto_tokenizer is None:
        raise ValueError(
            "Hugging Face support requires transformers AutoModelForCausalLM and AutoTokenizer"
        )
    return torch, auto_model_for_causal_lm, auto_tokenizer

###############################################################################
def load_huggingface_embedding_modules() -> tuple[Any, Any, Any]:
    auto_model = getattr(transformers, "AutoModel", None)
    auto_tokenizer = getattr(transformers, "AutoTokenizer", None)
    if auto_model is None or auto_tokenizer is None:
        raise ValueError(
            "Hugging Face embeddings require transformers AutoModel and AutoTokenizer"
        )
    return torch, auto_model, auto_tokenizer
