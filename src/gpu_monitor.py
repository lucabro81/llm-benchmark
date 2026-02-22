"""GPU monitoring using nvidia-smi for LLM inference benchmarking.

This module provides real-time GPU utilization and memory monitoring
by polling nvidia-smi during LLM inference operations.
"""

import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Tuple

# Configure logging
logger = logging.getLogger(__name__)


class GPUNotAvailableError(Exception):
    """Raised when nvidia-smi is not available or GPU access fails."""

    pass


@dataclass
class GPUMetrics:
    """GPU utilization and memory metrics collected during inference.

    Attributes:
        avg_utilization: Average GPU utilization percentage (0-100)
        peak_utilization: Peak GPU utilization percentage (0-100)
        avg_memory_used: Average GPU memory used in GB
        peak_memory_used: Peak GPU memory used in GB
        samples: Number of samples collected during monitoring
    """

    avg_utilization: float
    peak_utilization: float
    avg_memory_used: float
    peak_memory_used: float
    samples: int


def check_nvidia_smi_available() -> bool:
    """Check if nvidia-smi is available on the system.

    Returns:
        bool: True if nvidia-smi is accessible, False otherwise
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def parse_nvidia_smi_output(output: str) -> Tuple[float, float]:
    """Parse nvidia-smi CSV output to extract GPU metrics.

    Args:
        output: CSV output from nvidia-smi (format: "utilization, memory_mb")

    Returns:
        Tuple of (utilization_percent, memory_mb)

    Raises:
        ValueError: If output format is invalid or empty

    Example:
        >>> parse_nvidia_smi_output("85, 12345\\n")
        (85.0, 12345.0)
    """
    if not output or not output.strip():
        raise ValueError("nvidia-smi output is empty")

    lines = output.strip().split("\n")
    if not lines:
        raise ValueError("No data in nvidia-smi output")

    # Use first GPU if multiple GPUs present
    first_line = lines[0].strip()

    def _parse_field(raw: str) -> float:
        """Parse a single nvidia-smi field, treating [N/A] as 0.0."""
        value = raw.strip()
        if value == "[N/A]":
            return 0.0
        return float(value)

    try:
        parts = first_line.split(",")
        if len(parts) != 2:
            raise ValueError(f"Invalid CSV format: {first_line}")

        utilization = _parse_field(parts[0])
        memory_mb = _parse_field(parts[1])

        return utilization, memory_mb

    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse nvidia-smi output: {first_line}") from e


def monitor_gpu_during_inference(
    callback: Callable,
    polling_interval: float = 0.5,
) -> GPUMetrics:
    """Monitor GPU utilization and memory while callback executes.

    This function polls nvidia-smi at regular intervals while the callback
    function runs, collecting GPU utilization and memory usage samples.
    It then calculates average and peak metrics across all samples.

    Args:
        callback: Function to execute while monitoring GPU
        polling_interval: Time between nvidia-smi polls in seconds (default: 0.5)

    Returns:
        GPUMetrics: Aggregated GPU metrics from monitoring period

    Raises:
        GPUNotAvailableError: If nvidia-smi is not available
        Exception: Any exception raised by the callback is propagated

    Example:
        >>> def inference():
        ...     # Run LLM inference
        ...     return result
        >>> metrics = monitor_gpu_during_inference(inference)
        >>> print(f"Avg GPU: {metrics.avg_utilization}%")
    """
    # Check nvidia-smi availability
    if not check_nvidia_smi_available():
        raise GPUNotAvailableError(
            "nvidia-smi is not available. Ensure NVIDIA drivers are installed."
        )

    # Storage for GPU samples
    utilization_samples: List[float] = []
    memory_samples: List[float] = []
    monitoring_active = threading.Event()
    monitoring_active.set()

    def poll_gpu():
        """Poll nvidia-smi in background thread."""
        while monitoring_active.is_set():
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu,memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    utilization, memory_mb = parse_nvidia_smi_output(result.stdout)
                    utilization_samples.append(utilization)
                    memory_samples.append(memory_mb)
                else:
                    logger.warning(f"nvidia-smi returned error: {result.returncode}")

            except Exception as e:
                logger.warning(f"Failed to poll nvidia-smi: {e}")

            # Wait before next poll
            time.sleep(polling_interval)

    # Start monitoring thread
    monitor_thread = threading.Thread(target=poll_gpu, daemon=True)
    monitor_thread.start()

    try:
        # Execute callback while monitoring
        callback_result = callback()

    finally:
        # Stop monitoring
        monitoring_active.clear()
        monitor_thread.join(timeout=2.0)

    # Calculate metrics from samples
    if not utilization_samples:
        logger.warning(
            "No GPU samples collected. Callback may have finished too quickly."
        )
        return GPUMetrics(
            avg_utilization=0.0,
            peak_utilization=0.0,
            avg_memory_used=0.0,
            peak_memory_used=0.0,
            samples=0,
        )

    avg_utilization = sum(utilization_samples) / len(utilization_samples)
    peak_utilization = max(utilization_samples)

    # Convert memory from MB to GB
    avg_memory_gb = sum(memory_samples) / len(memory_samples) / 1024
    peak_memory_gb = max(memory_samples) / 1024

    metrics = GPUMetrics(
        avg_utilization=avg_utilization,
        peak_utilization=peak_utilization,
        avg_memory_used=avg_memory_gb,
        peak_memory_used=peak_memory_gb,
        samples=len(utilization_samples),
    )

    logger.info(
        f"GPU monitoring complete: {metrics.samples} samples, "
        f"avg={avg_utilization:.1f}%, peak={peak_utilization:.1f}%"
    )

    return metrics
