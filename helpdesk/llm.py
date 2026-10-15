"""LiteLLM model factory for Ollama-hosted chat models."""

from google.adk.models.lite_llm import LiteLlm

from helpdesk import config

# Tool schemas + system prompt + 5 retrieved passages overflow Ollama's default context
NUM_CTX = 8192


def make_model(model: str | None = None) -> LiteLlm:
    name = model or config.MODEL
    kwargs = {"num_ctx": NUM_CTX, "temperature": config.TEMPERATURE}
    if "qwen3" in name:
        # Otherwise qwen3 writes its reasoning into the final answer (and is ~10x slower).
        # Only thinking-capable models accept this flag; Ollama rejects it for llama3.1.
        kwargs["think"] = False
    return LiteLlm(model=name, **kwargs)
