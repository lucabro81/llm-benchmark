"""Tests for gpu_monitor module following TDD approach."""

import time
from dataclasses import is_dataclass
from unittest.mock import Mock, patch

import pytest

from src.gpu_monitor import (
    GPUMetrics,
    GPUNotAvailableError,
    check_nvidia_smi_available,
    monitor_gpu_during_inference,
    parse_nvidia_smi_output,
)


class TestGPUMetricsDataclass:
    """Test GPUMetrics dataclass structure and properties."""

    def test_gpu_metrics_is_dataclass(self):
        """GPUMetrics should be a dataclass."""
        assert is_dataclass(GPUMetrics)

    def test_gpu_metrics_complete_data(self):
        """GPUMetrics should store all GPU monitoring data."""
        metrics = GPUMetrics(
            avg_utilization=85.5,
            peak_utilization=98.2,
            avg_memory_used=11.4,
            peak_memory_used=12.1,
            samples=10,
        )

        assert metrics.avg_utilization == 85.5
        assert metrics.peak_utilization == 98.2
        assert metrics.avg_memory_used == 11.4
        assert metrics.peak_memory_used == 12.1
        assert metrics.samples == 10

    def test_gpu_metrics_zero_samples(self):
        """GPUMetrics should handle zero samples case."""
        metrics = GPUMetrics(
            avg_utilization=0.0,
            peak_utilization=0.0,
            avg_memory_used=0.0,
            peak_memory_used=0.0,
            samples=0,
        )

        assert metrics.samples == 0
        assert metrics.avg_utilization == 0.0


class TestNvidiaSmiAvailability:
    """Test nvidia-smi availability checking."""

    @patch("subprocess.run")
    def test_nvidia_smi_available(self, mock_run):
        """Should return True when nvidia-smi is available."""
        mock_run.return_value = Mock(returncode=0)

        assert check_nvidia_smi_available() is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_nvidia_smi_not_available(self, mock_run):
        """Should return False when nvidia-smi is not found."""
        mock_run.side_effect = FileNotFoundError()

        assert check_nvidia_smi_available() is False

    @patch("subprocess.run")
    def test_nvidia_smi_error(self, mock_run):
        """Should return False when nvidia-smi returns error."""
        mock_run.return_value = Mock(returncode=1)

        assert check_nvidia_smi_available() is False


class TestNvidiaSmiParsing:
    """Test parsing of nvidia-smi CSV output."""

    def test_parse_valid_output(self):
        """Should parse valid nvidia-smi CSV output."""
        output = "85, 12345\n"  # 85% GPU, 12345 MB VRAM

        utilization, memory_mb = parse_nvidia_smi_output(output)

        assert utilization == 85.0
        assert memory_mb == 12345.0

    def test_parse_multiple_lines(self):
        """Should parse first line when multiple GPUs present."""
        output = "85, 12345\n90, 15000\n"

        utilization, memory_mb = parse_nvidia_smi_output(output)

        # Should use first GPU
        assert utilization == 85.0
        assert memory_mb == 12345.0

    def test_parse_with_whitespace(self):
        """Should handle extra whitespace in output."""
        output = "  85 ,  12345  \n"

        utilization, memory_mb = parse_nvidia_smi_output(output)

        assert utilization == 85.0
        assert memory_mb == 12345.0

    def test_parse_zero_utilization(self):
        """Should handle zero GPU utilization."""
        output = "0, 1024\n"

        utilization, memory_mb = parse_nvidia_smi_output(output)

        assert utilization == 0.0
        assert memory_mb == 1024.0

    def test_parse_empty_output(self):
        """Should raise error for empty output."""
        with pytest.raises(ValueError):
            parse_nvidia_smi_output("")

    def test_parse_invalid_format(self):
        """Should raise error for invalid CSV format."""
        with pytest.raises(ValueError):
            parse_nvidia_smi_output("invalid output")


class TestMonitorGPUDuringInference:
    """Test GPU monitoring during callback execution."""

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    def test_raises_error_if_nvidia_smi_unavailable(self, mock_check):
        """Should raise GPUNotAvailableError if nvidia-smi is not available."""
        mock_check.return_value = False

        def dummy_callback():
            return "result"

        with pytest.raises(GPUNotAvailableError):
            monitor_gpu_during_inference(dummy_callback)

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_monitors_gpu_during_callback(self, mock_run, mock_check):
        """Should monitor GPU while callback executes."""
        mock_check.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="85, 12345\n",
        )

        def slow_callback():
            time.sleep(0.1)
            return "done"

        result = monitor_gpu_during_inference(slow_callback)

        assert isinstance(result, GPUMetrics)
        assert result.samples > 0  # Should have captured at least one sample
        assert result.avg_utilization >= 0
        assert result.peak_utilization >= 0

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_calculates_average_metrics(self, mock_run, mock_check):
        """Should calculate average utilization and memory correctly."""
        mock_check.return_value = True

        # Simulate multiple readings
        outputs = [
            "80, 10000\n",
            "90, 12000\n",
            "85, 11000\n",
        ]
        mock_run.side_effect = [Mock(returncode=0, stdout=out) for out in outputs]

        def quick_callback():
            # Allow time for multiple samples
            time.sleep(0.05)
            return "done"

        result = monitor_gpu_during_inference(quick_callback, polling_interval=0.01)

        # With 3 samples: avg_util = (80+90+85)/3 = 85.0
        # avg_mem = (10000+12000+11000)/3 = 11000.0 MB = 10.74 GB
        assert result.samples == 3
        assert result.avg_utilization == 85.0
        assert result.peak_utilization == 90.0
        assert abs(result.avg_memory_used - 10.74) < 0.1  # ~10.74 GB (11000 MB / 1024)
        assert abs(result.peak_memory_used - 11.72) < 0.1  # ~11.72 GB (12000 MB / 1024)

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_handles_callback_exceptions(self, mock_run, mock_check):
        """Should stop monitoring if callback raises exception."""
        mock_check.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="85, 12345\n")

        def failing_callback():
            time.sleep(0.05)
            raise ValueError("Callback failed")

        with pytest.raises(ValueError):
            monitor_gpu_during_inference(failing_callback)

        # Monitoring should have stopped after exception

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_custom_polling_interval(self, mock_run, mock_check):
        """Should respect custom polling interval."""
        mock_check.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="85, 12345\n")

        def callback():
            time.sleep(0.05)
            return "done"

        # With 1 second interval, should get only 1 sample in 0.05s
        result = monitor_gpu_during_inference(callback, polling_interval=1.0)

        assert result.samples <= 2  # At most 1-2 samples with long interval

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_nvidia_smi_command_format(self, mock_run, mock_check):
        """Should call nvidia-smi with correct parameters."""
        mock_check.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="85, 12345\n")

        def quick_callback():
            return "done"

        monitor_gpu_during_inference(quick_callback)

        # Verify nvidia-smi was called with correct arguments
        call_args = mock_run.call_args[0][0]
        assert "nvidia-smi" in call_args
        assert "--query-gpu=utilization.gpu,memory.used" in " ".join(call_args)
        assert "--format=csv,noheader,nounits" in " ".join(call_args)


class TestGPUMonitorEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_zero_samples_warning(self, mock_run, mock_check):
        """Should handle case where no samples were captured."""
        mock_check.return_value = True

        def instant_callback():
            # Returns instantly, may not capture any samples
            return "done"

        result = monitor_gpu_during_inference(instant_callback, polling_interval=1.0)

        # Should return valid metrics even with 0 samples
        assert isinstance(result, GPUMetrics)
        # If no samples, should have default values
        if result.samples == 0:
            assert result.avg_utilization == 0.0
            assert result.peak_utilization == 0.0

    @patch("src.gpu_monitor.check_nvidia_smi_available")
    @patch("subprocess.run")
    def test_nvidia_smi_intermittent_failures(self, mock_run, mock_check):
        """Should skip failed nvidia-smi calls but continue monitoring."""
        mock_check.return_value = True

        # Mix of successful and failed calls
        mock_run.side_effect = [
            Mock(returncode=0, stdout="80, 10000\n"),
            Mock(returncode=1, stdout=""),  # Failed call
            Mock(returncode=0, stdout="90, 12000\n"),
        ]

        def callback():
            time.sleep(0.05)
            return "done"

        result = monitor_gpu_during_inference(callback, polling_interval=0.01)

        # Should have 2 successful samples (skipping the failed one)
        assert result.samples == 2
        assert result.avg_utilization == 85.0  # (80+90)/2


class TestGPUMonitorIntegration:
    """Integration tests (require actual nvidia-smi)."""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires NVIDIA GPU with drivers")
    def test_real_gpu_monitoring(self):
        """Integration test with real nvidia-smi."""

        def compute_task():
            # Simulate some work
            total = 0
            for i in range(1000000):
                total += i
            return total

        result = monitor_gpu_during_inference(compute_task)

        assert result.samples > 0
        assert result.avg_utilization >= 0
        assert result.avg_memory_used > 0
        print(f"GPU Metrics: {result}")
