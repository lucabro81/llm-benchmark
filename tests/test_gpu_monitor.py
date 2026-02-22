"""Tests for gpu_monitor module."""

import time
from unittest.mock import Mock, patch

import pytest

from src.gpu_monitor import (
    GPUMetrics,
    GPUNotAvailableError,
    check_nvidia_smi_available,
    monitor_gpu_during_inference,
    parse_nvidia_smi_output,
)


class TestNvidiaSmiAvailability:
    """Test nvidia-smi availability checking."""

    @patch("subprocess.run")
    def test_nvidia_smi_available(self, mock_run):
        """Should return True when nvidia-smi is available."""
        mock_run.return_value = Mock(returncode=0)
        assert check_nvidia_smi_available() is True

    @patch("subprocess.run")
    def test_nvidia_smi_not_found(self, mock_run):
        """Should return False when nvidia-smi binary is not found."""
        mock_run.side_effect = FileNotFoundError()
        assert check_nvidia_smi_available() is False

    @patch("subprocess.run")
    def test_nvidia_smi_error(self, mock_run):
        """Should return False when nvidia-smi returns non-zero exit code."""
        mock_run.return_value = Mock(returncode=1)
        assert check_nvidia_smi_available() is False


class TestNvidiaSmiParsing:
    """Test parsing of nvidia-smi CSV output."""

    def test_parse_valid_output(self):
        """Should parse valid CSV output into (utilization%, memory_mb)."""
        utilization, memory_mb = parse_nvidia_smi_output("85, 12345\n")
        assert utilization == 85.0
        assert memory_mb == 12345.0

    def test_parse_uses_first_gpu_when_multiple_present(self):
        """Should use first line when multiple GPUs are reported."""
        utilization, memory_mb = parse_nvidia_smi_output("85, 12345\n90, 15000\n")
        assert utilization == 85.0
        assert memory_mb == 12345.0

    def test_parse_strips_whitespace(self):
        """Should handle extra whitespace around values."""
        utilization, memory_mb = parse_nvidia_smi_output("  85 ,  12345  \n")
        assert utilization == 85.0
        assert memory_mb == 12345.0

    def test_parse_zero_utilization(self):
        """Should handle zero GPU utilization (idle GPU)."""
        utilization, memory_mb = parse_nvidia_smi_output("0, 1024\n")
        assert utilization == 0.0
        assert memory_mb == 1024.0

    def test_parse_empty_output_raises(self):
        """Should raise ValueError for empty output."""
        with pytest.raises(ValueError):
            parse_nvidia_smi_output("")

    def test_parse_invalid_format_raises(self):
        """Should raise ValueError for non-CSV output."""
        with pytest.raises(ValueError):
            parse_nvidia_smi_output("invalid output")


class TestMonitorGPUDuringInference:
    """Test GPU monitoring during callback execution."""

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    def test_raises_if_nvidia_smi_unavailable(self, mock_check):
        """Should raise GPUNotAvailableError when nvidia-smi is missing."""
        mock_check.return_value = False
        with pytest.raises(GPUNotAvailableError):
            monitor_gpu_during_inference(lambda: None)

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_calculates_avg_and_peak_correctly(self, mock_run, mock_check):
        """Should compute avg/peak utilization and memory from samples."""
        mock_check.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="80, 10000\n"),
            Mock(returncode=0, stdout="90, 12000\n"),
            Mock(returncode=0, stdout="85, 11000\n"),
        ]

        result = monitor_gpu_during_inference(
            lambda: time.sleep(0.05), polling_interval=0.01
        )

        assert result.samples == 3
        assert result.avg_utilization == 85.0
        assert result.peak_utilization == 90.0
        assert abs(result.avg_memory_used - 10.74) < 0.1   # 11000 MB avg / 1024
        assert abs(result.peak_memory_used - 11.72) < 0.1  # 12000 MB peak / 1024

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_skips_failed_samples_continues_monitoring(self, mock_run, mock_check):
        """Should skip nvidia-smi errors but keep collecting remaining samples."""
        mock_check.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="80, 10000\n"),
            Mock(returncode=1, stdout=""),   # failed poll
            Mock(returncode=0, stdout="90, 12000\n"),
        ]

        result = monitor_gpu_during_inference(
            lambda: time.sleep(0.05), polling_interval=0.01
        )

        assert result.samples == 2
        assert result.avg_utilization == 85.0  # (80+90)/2

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_propagates_callback_exception(self, mock_run, mock_check):
        """Should stop monitoring and re-raise any exception from callback."""
        mock_check.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="85, 12345\n")

        def failing():
            time.sleep(0.05)
            raise ValueError("boom")

        with pytest.raises(ValueError):
            monitor_gpu_during_inference(failing)

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_returns_zero_metrics_when_no_samples_collected(self, mock_run, mock_check):
        """Should return zeroed GPUMetrics when callback finishes before first poll."""
        mock_check.return_value = True

        result = monitor_gpu_during_inference(lambda: None, polling_interval=10.0)

        assert isinstance(result, GPUMetrics)
        if result.samples == 0:
            assert result.avg_utilization == 0.0
            assert result.peak_utilization == 0.0

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_calls_nvidia_smi_with_correct_arguments(self, mock_run, mock_check):
        """Should invoke nvidia-smi with query-gpu and csv format flags."""
        mock_check.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="85, 12345\n")

        monitor_gpu_during_inference(lambda: None)

        call_args = mock_run.call_args[0][0]
        assert "nvidia-smi" in call_args
        assert "--query-gpu=utilization.gpu,memory.used" in " ".join(call_args)
        assert "--format=csv,noheader,nounits" in " ".join(call_args)


class TestGPUMonitorIntegration:
    """Integration tests (require actual nvidia-smi)."""

    @pytest.mark.integration
    def test_real_gpu_monitoring(self):
        """Integration test with real nvidia-smi."""
        result = monitor_gpu_during_inference(lambda: time.sleep(1))
        assert result.samples > 0
        assert result.avg_utilization >= 0
        assert result.avg_memory_used > 0
