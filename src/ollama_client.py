"""Ollama API client with error handling and metrics extraction.

This module provides a wrapper around the Ollama Python SDK for making
chat completion requests with proper error handling, timeout support,
and performance metrics extraction.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import ollama
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


# Custom exceptions
class ModelNotFoundError(Exception):
    """Raised when the specified model is not found in Ollama."""

    pass


class OllamaConnectionError(Exception):
    """Raised when unable to connect to Ollama API."""

    pass


class TimeoutError(Exception):
    """Raised when Ollama request exceeds timeout."""

    pass


@dataclass
class ChatResult:
    """Result from an Ollama chat completion request.

    Attributes:
        response_text: The generated text response from the model
        duration_sec: Total duration of the request in seconds
        tokens_generated: Number of tokens generated in the response
        tokens_per_sec: Generation speed in tokens per second
        success: Whether the request completed successfully
        error: Error message if request failed, None otherwise
    """

    response_text: str
    duration_sec: float
    tokens_generated: int
    tokens_per_sec: float
    success: bool
    error: Optional[str] = None


def get_ollama_base_url() -> str:
    """Get Ollama base URL from environment or use default.

    Returns:
        str: Ollama base URL (e.g., 'http://localhost:11434')

    Environment Variables:
        OLLAMA_BASE_URL: Custom Ollama server URL (optional)
    """
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def chat(model: str, prompt: str, timeout: int = 30) -> ChatResult:
    """Call Ollama chat API and return structured result.

    Args:
        model: Name of the Ollama model to use (e.g., 'qwen2.5-coder:7b')
        prompt: The input prompt/question for the model
        timeout: Maximum time to wait for response in seconds (default: 30)

    Returns:
        ChatResult: Structured result containing response and metrics

    Raises:
        ModelNotFoundError: If the specified model is not found
        OllamaConnectionError: If unable to connect to Ollama API
        TimeoutError: If request exceeds timeout duration
        Exception: For other unexpected errors

    Example:
        >>> result = chat(
        ...     model="qwen2.5-coder:7b",
        ...     prompt="Write a hello world function",
        ...     timeout=30
        ... )
        >>> print(result.response_text)
        >>> print(f"Speed: {result.tokens_per_sec:.1f} tok/s")
    """
    try:
        logger.info(f"Calling Ollama model '{model}' with timeout={timeout}s")

        # Call Ollama API
        # Note: The official ollama Python SDK doesn't directly support timeout
        # For MVP, we'll use the default behavior and handle in future iteration
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract response text
        response_text = response.get("message", {}).get("content", "")

        # Extract timing metadata (values are in nanoseconds)
        eval_duration_ns = response.get("eval_duration", 0)
        duration_sec = eval_duration_ns / 1_000_000_000 if eval_duration_ns else 0.0

        # Extract token count
        tokens_generated = response.get("eval_count", 0)

        # Calculate tokens per second
        tokens_per_sec = (
            tokens_generated / duration_sec if duration_sec > 0 else 0.0
        )

        logger.info(
            f"Success: {tokens_generated} tokens in {duration_sec:.2f}s "
            f"({tokens_per_sec:.1f} tok/s)"
        )

        return ChatResult(
            response_text=response_text,
            duration_sec=duration_sec,
            tokens_generated=tokens_generated,
            tokens_per_sec=tokens_per_sec,
            success=True,
            error=None,
        )

    except Exception as e:
        error_msg = str(e).lower()

        # Parse error type and raise appropriate exception
        if "not found" in error_msg or "does not exist" in error_msg:
            logger.error(f"Model not found: {model}")
            raise ModelNotFoundError(f"Model '{model}' not found in Ollama") from e

        if "connection" in error_msg or "refused" in error_msg:
            logger.error(f"Connection error to Ollama at {get_ollama_base_url()}")
            raise OllamaConnectionError(
                f"Connection error to Ollama API at {get_ollama_base_url()}"
            ) from e

        if "timeout" in error_msg or "timed out" in error_msg:
            logger.error(f"Request timeout after {timeout}s")
            raise TimeoutError(f"Ollama request exceeded timeout of {timeout}s") from e

        # Log and re-raise unexpected errors
        logger.error(f"Unexpected error calling Ollama: {e}", exc_info=True)
        raise
