"""Tests for ollama_client module."""

import os
from unittest.mock import Mock, patch

import pytest

from src.common.ollama_client import (
    ModelNotFoundError,
    OllamaConnectionError,
    TimeoutError,
    chat,
    get_ollama_base_url,
)


class TestOllamaConfiguration:
    """Test Ollama base URL configuration from environment."""

    def test_default_ollama_url(self):
        """Should return localhost:11434 when no env var is set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_ollama_base_url() == "http://localhost:11434"

    def test_custom_ollama_url_from_env(self):
        """Should return custom URL when OLLAMA_BASE_URL is set."""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://192.168.1.100:11434"}):
            assert get_ollama_base_url() == "http://192.168.1.100:11434"


class TestChatFunction:
    """Test chat() — metadata extraction and tokens/sec calculation."""

    @patch("src.common.ollama_client.ollama.chat")
    def test_parses_nanoseconds_to_seconds(self, mock_chat):
        """Should convert eval_duration from nanoseconds to seconds."""
        mock_chat.return_value = {
            "message": {"content": "hello"},
            "eval_duration": 2_500_000_000,  # 2.5 billion ns = 2.5s
            "eval_count": 10,
        }

        result = chat(model="test", prompt="test")

        assert result.duration_sec == 2.5

    @patch("src.common.ollama_client.ollama.chat")
    def test_calculates_tokens_per_sec(self, mock_chat):
        """Should derive tokens/sec from eval_count / duration."""
        mock_chat.return_value = {
            "message": {"content": "hello"},
            "eval_duration": 2_500_000_000,  # 2.5s
            "eval_count": 10,
        }

        result = chat(model="test", prompt="test")

        assert result.tokens_per_sec == 4.0  # 10 / 2.5

    @patch("src.common.ollama_client.ollama.chat")
    def test_handles_missing_metadata_with_defaults(self, mock_chat):
        """Should return 0 for metrics when response lacks timing metadata."""
        mock_chat.return_value = {
            "message": {"content": "response"},
            # no eval_duration, no eval_count
        }

        result = chat(model="test", prompt="test")

        assert result.success is True
        assert result.duration_sec == 0.0
        assert result.tokens_generated == 0
        assert result.tokens_per_sec == 0.0

    @patch("src.common.ollama_client.ollama.chat")
    def test_passes_model_and_prompt_to_api(self, mock_chat):
        """Should forward model name and prompt to the Ollama SDK."""
        mock_chat.return_value = {
            "message": {"content": "ok"},
            "eval_duration": 1_000_000_000,
            "eval_count": 5,
        }

        chat(model="qwen2.5-coder:7b", prompt="Say hello")

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "qwen2.5-coder:7b"
        assert call_kwargs["messages"][0]["content"] == "Say hello"


class TestChatErrorHandling:
    """Test that Ollama error messages are mapped to correct exception types."""

    @patch("src.common.ollama_client.ollama.chat")
    def test_model_not_found_raises_correct_exception(self, mock_chat):
        """Should raise ModelNotFoundError for 'not found' errors."""
        mock_chat.side_effect = Exception("model 'nonexistent:latest' not found")

        with pytest.raises(ModelNotFoundError) as exc_info:
            chat(model="nonexistent:latest", prompt="test")

        assert "nonexistent:latest" in str(exc_info.value)

    @patch("src.common.ollama_client.ollama.chat")
    def test_connection_refused_raises_correct_exception(self, mock_chat):
        """Should raise OllamaConnectionError for connection errors."""
        mock_chat.side_effect = Exception("connection refused")

        with pytest.raises(OllamaConnectionError):
            chat(model="test", prompt="test")

    @patch("src.common.ollama_client.ollama.chat")
    def test_timeout_raises_correct_exception(self, mock_chat):
        """Should raise TimeoutError for timeout errors."""
        mock_chat.side_effect = Exception("timeout exceeded")

        with pytest.raises(TimeoutError):
            chat(model="test", prompt="test", timeout=5)


class TestChatIntegration:
    """Integration tests (require running Ollama instance)."""

    @pytest.mark.integration
    def test_real_ollama_call(self):
        """Integration test with real Ollama."""
        result = chat(
            model="qwen2.5-coder:7b-instruct-q8_0",
            prompt="Say 'test successful' and nothing else",
            timeout=30,
        )
        assert result.success is True
        assert len(result.response_text) > 0
        assert result.tokens_per_sec > 0
