import logging
import os

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# Configurable from Django settings (which reads from .env)
# Default: 1536 (OpenAI text-embedding-3-small). If using HF, set to match your model.
EMBEDDING_DIMENSIONS = getattr(settings, "EMBEDDING_DIMENSIONS", 1536)


def _resolve_hf_token() -> str:
    """Return HF token, checking multiple env var names."""
    return (
        getattr(settings, "HF_TOKEN", "")
        or os.getenv("HF_TOKEN", "")
        or getattr(settings, "LLM_API_KEY", "")
        or os.getenv("LLM_API_KEY", "")
    )


def _hf_embedding_model() -> str:
    return getattr(settings, "HF_EMBEDDING_MODEL", "") or os.getenv("HF_EMBEDDING_MODEL", "")


def _openai_api_key() -> str:
    return getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")


def _openai_embedding_model() -> str:
    return (
        getattr(settings, "OPENAI_EMBEDDING_MODEL", "")
        or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )


def _safe_embedding_call(func, *args, **kwargs) -> list[float] | None:
    """Call an embedding function and return None on any HTTP/network error.

    This prevents the entire system from crashing when an embedding provider
    is unreachable (e.g., during Docker startup when DNS/network isn't ready).
    """
    try:
        return func(*args, **kwargs)
    except httpx.HTTPStatusError as e:
        logger.warning("Embedding API HTTP error %s: %s", e.response.status_code, e)
    except httpx.ConnectError as e:
        logger.warning("Embedding API connection error (network unreachable): %s", e)
    except httpx.TimeoutException as e:
        logger.warning("Embedding API timeout: %s", e)
    except httpx.HTTPError as e:
        logger.warning("Embedding API HTTP error: %s", e)
    except Exception as e:
        logger.warning("Embedding API unexpected error: %s (%s)", type(e).__name__, e)
    return None


def _get_hf_embedding(text: str, token: str, model: str) -> list[float]:
    """Get embedding using Hugging Face Inference API (OpenAI-compatible endpoint)."""
    with httpx.Client() as client:
        response = client.post(
            "https://api-inference.huggingface.co/v1/embeddings",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": model, "input": text},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


def _get_hf_embeddings_batch(texts: list[str], token: str, model: str) -> list[list[float]]:
    """Get embeddings for multiple texts via HF Inference API."""
    with httpx.Client() as client:
        response = client.post(
            "https://api-inference.huggingface.co/v1/embeddings",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": model, "input": texts},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]


def _get_openai_embedding(text: str, api_key: str, model: str) -> list[float]:
    """Get embedding using OpenAI API."""
    with httpx.Client() as client:
        response = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": text},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


def _get_openai_embeddings_batch(texts: list[str], api_key: str, model: str) -> list[list[float]]:
    """Get embeddings for multiple texts via OpenAI API."""
    with httpx.Client() as client:
        response = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": texts},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]


def get_embedding(text: str) -> list[float]:
    """Get embedding for a single text.

    Provider priority:
    1. Hugging Face (if HF_TOKEN + HF_EMBEDDING_MODEL are set)
    2. OpenAI (if OPENAI_API_KEY is set)
    3. Dummy zero vector (fallback)
    """
    hf_token = _resolve_hf_token()
    hf_model = _hf_embedding_model()
    if hf_token and hf_model:
        logger.debug("Using Hugging Face embedding model: %s", hf_model)
        result = _safe_embedding_call(_get_hf_embedding, text, hf_token, hf_model)
        if result is not None:
            return result
        logger.warning("Hugging Face embedding failed, falling back to zero vector")
        return [0.0] * EMBEDDING_DIMENSIONS

    openai_key = _openai_api_key()
    if openai_key:
        model = _openai_embedding_model()
        logger.debug("Using OpenAI embedding model: %s", model)
        result = _safe_embedding_call(_get_openai_embedding, text, openai_key, model)
        if result is not None:
            return result
        logger.warning("OpenAI embedding failed, falling back to zero vector")
        return [0.0] * EMBEDDING_DIMENSIONS

    logger.warning("No embedding provider configured (set HF_EMBEDDING_MODEL or OPENAI_API_KEY), using dummy embedding")
    return [0.0] * EMBEDDING_DIMENSIONS


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts.

    Provider priority:
    1. Hugging Face (if HF_TOKEN + HF_EMBEDDING_MODEL are set)
    2. OpenAI (if OPENAI_API_KEY is set)
    3. Dummy zero vectors (fallback)

    On API/network error, gracefully falls back to the next provider or zero vectors.
    """
    hf_token = _resolve_hf_token()
    hf_model = _hf_embedding_model()
    if hf_token and hf_model:
        logger.debug("Using Hugging Face batch embedding model: %s", hf_model)
        result = _safe_embedding_call(_get_hf_embeddings_batch, texts, hf_token, hf_model)
        if result is not None:
            return result
        logger.warning("Hugging Face batch embedding failed, falling back to zero vectors")
        return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]

    openai_key = _openai_api_key()
    if openai_key:
        model = _openai_embedding_model()
        logger.debug("Using OpenAI batch embedding model: %s", model)
        result = _safe_embedding_call(_get_openai_embeddings_batch, texts, openai_key, model)
        if result is not None:
            return result
        logger.warning("OpenAI batch embedding failed, falling back to zero vectors")
        return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]

    logger.warning("No embedding provider configured, using dummy embeddings")
    return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]