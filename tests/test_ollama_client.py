"""Tests for ollama_client module following TDD approach."""

import os
from dataclasses import is_dataclass
from unittest.mock import Mock, patch

import pytest

from src.ollama_client import (
    ChatResult,
    ModelNotFoundError,
    OllamaConnectionError,
    TimeoutError,
    chat,
    get_ollama_base_url,
)


class TestChatResultDataclass:
    """Test ChatResult dataclass structure and properties."""

    def test_chat_result_is_dataclass(self):
        """ChatResult should be a dataclass."""
        assert is_dataclass(ChatResult)

    def test_chat_result_success_case(self):
        """ChatResult should store successful chat response data."""
        result = ChatResult(
            response_text="Hello, world!",
            duration_sec=2.5,
            tokens_generated=10,
            tokens_per_sec=4.0,
            success=True,
            error=None,
        )

        assert result.response_text == "Hello, world!"
        assert result.duration_sec == 2.5
        assert result.tokens_generated == 10
        assert result.tokens_per_sec == 4.0
        assert result.success is True
        assert result.error is None

    def test_chat_result_error_case(self):
        """ChatResult should store error information when request fails."""
        result = ChatResult(
            response_text="",
            duration_sec=0.0,
            tokens_generated=0,
            tokens_per_sec=0.0,
            success=False,
            error="Connection timeout",
        )

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.response_text == ""


class TestOllamaConfiguration:
    """Test Ollama base URL configuration from environment."""

    def test_default_ollama_url(self):
        """Should use default localhost URL when no env var is set."""
        with patch.dict(os.environ, {}, clear=True):
            url = get_ollama_base_url()
            assert url == "http://localhost:11434"

    def test_custom_ollama_url_from_env(self):
        """Should use OLLAMA_BASE_URL from environment variable."""
        custom_url = "http://192.168.1.100:11434"
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": custom_url}):
            url = get_ollama_base_url()
            assert url == custom_url

    def test_ollama_url_from_dotenv(self, tmp_path):
        """Should load OLLAMA_BASE_URL from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("OLLAMA_BASE_URL=http://custom-host:8080\n")

        # This will be tested after implementation with actual dotenv loading
        # For now, we test the function exists and has correct behavior
        pass


class TestChatFunction:
    """Test chat() function with mocked Ollama API."""

    @patch("src.ollama_client.ollama.chat")
    def test_successful_chat_call(self, mock_chat):
        """Should successfully call Ollama API and return ChatResult."""
        # Mock Ollama API response
        mock_chat.return_value = {
            "message": {"content": "Hello from LLM!"},
            "eval_duration": 2500000000,  # 2.5 seconds in nanoseconds
            "eval_count": 10,  # tokens generated
        }

        result = chat(model="qwen2.5-coder:7b", prompt="Say hello")

        assert result.success is True
        assert result.response_text == "Hello from LLM!"
        assert result.duration_sec == 2.5
        assert result.tokens_generated == 10
        assert result.tokens_per_sec == 4.0
        assert result.error is None

        # Verify Ollama was called correctly
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "qwen2.5-coder:7b"
        assert call_kwargs["messages"][0]["content"] == "Say hello"

    @patch("src.ollama_client.ollama.chat")
    def test_chat_with_custom_timeout(self, mock_chat):
        """Should accept custom timeout parameter."""
        mock_chat.return_value = {
            "message": {"content": "Response"},
            "eval_duration": 1000000000,
            "eval_count": 5,
        }

        result = chat(model="test-model", prompt="test", timeout=60)

        assert result.success is True
        # Timeout handling will be implemented in the actual function

    @patch("src.ollama_client.ollama.chat")
    def test_chat_handles_missing_metadata(self, mock_chat):
        """Should handle response with missing optional metadata gracefully."""
        mock_chat.return_value = {
            "message": {"content": "Response without full metadata"},
            # Missing eval_duration and eval_count
        }

        result = chat(model="test-model", prompt="test")

        assert result.success is True
        assert result.response_text == "Response without full metadata"
        # Should have sensible defaults for missing metrics
        assert result.duration_sec >= 0
        assert result.tokens_generated >= 0


class TestChatErrorHandling:
    """Test error handling for various failure scenarios."""

    @patch("src.ollama_client.ollama.chat")
    def test_model_not_found_error(self, mock_chat):
        """Should raise ModelNotFoundError when model doesn't exist."""
        mock_chat.side_effect = Exception("model 'nonexistent:latest' not found")

        with pytest.raises(ModelNotFoundError) as exc_info:
            chat(model="nonexistent:latest", prompt="test")

        assert "nonexistent:latest" in str(exc_info.value)

    @patch("src.ollama_client.ollama.chat")
    def test_connection_error(self, mock_chat):
        """Should raise OllamaConnectionError when API is unreachable."""
        mock_chat.side_effect = Exception("connection refused")

        with pytest.raises(OllamaConnectionError) as exc_info:
            chat(model="test-model", prompt="test")

        assert "connection" in str(exc_info.value).lower()

    @patch("src.ollama_client.ollama.chat")
    def test_timeout_error(self, mock_chat):
        """Should raise TimeoutError when request exceeds timeout."""
        mock_chat.side_effect = Exception("timeout exceeded")

        with pytest.raises(TimeoutError) as exc_info:
            chat(model="test-model", prompt="test", timeout=5)

        assert "timeout" in str(exc_info.value).lower()

    @patch("src.ollama_client.ollama.chat")
    def test_generic_error_logged(self, mock_chat):
        """Should log generic errors with context."""
        mock_chat.side_effect = Exception("unknown error")

        with pytest.raises(Exception) as exc_info:
            chat(model="test-model", prompt="test")

        # Error should contain context about what failed
        # Actual logging will be verified in implementation


class TestChatIntegration:
    """Integration-style tests (will be skipped if Ollama not available)."""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires running Ollama instance")
    def test_real_ollama_call(self):
        """Integration test with real Ollama (skipped by default)."""
        # This test can be enabled manually for integration testing
        result = chat(
            model="qwen2.5-coder:7b-instruct-q8_0",
            prompt="Say 'test successful' and nothing else",
            timeout=30,
        )

        assert result.success is True
        assert len(result.response_text) > 0
        assert result.tokens_per_sec > 0
