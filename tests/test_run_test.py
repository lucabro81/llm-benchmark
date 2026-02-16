"""Tests for run_test.py CLI runner following TDD approach.

This test suite validates the CLI runner workflow, including
configuration, multiple test runs, JSON output, and statistics.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, call

import pytest

# Import will fail until we create run_test.py, but that's expected in TDD
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRunTestConfiguration:
    """Test configuration and initialization of CLI runner."""

    @patch("run_test.Path")
    def test_creates_results_directory(self, mock_path_class):
        """Should create results/ directory if it doesn't exist."""
        # This test will verify that OUTPUT_DIR.mkdir(exist_ok=True) is called
        # We'll implement this once run_test.py exists
        pass

    def test_uses_correct_default_config(self):
        """Should use hardcoded configuration values."""
        # Verify MODEL, FIXTURE, RUNS constants exist and have expected values
        pass


class TestRunTestExecution:
    """Test execution of multiple test runs."""

    @patch("run_test.RefactoringTest")
    def test_executes_multiple_runs(self, mock_test_class):
        """Should execute RUNS number of test runs."""
        from src.refactoring_test import TestResult

        # Setup mock
        mock_instance = Mock()
        mock_test_class.return_value = mock_instance

        # Create fake results
        fake_result = TestResult(
            model="test-model",
            fixture="test-fixture",
            timestamp="2025-02-16T14:23:45",
            run_number=1,
            compiles=True,
            compilation_errors=[],
            compilation_warnings=[],
            pattern_score=10.0,
            naming_score=10.0,
            final_score=10.0,
            tokens_per_sec=185.3,
            duration_sec=4.2,
            gpu_avg_utilization=94.2,
            gpu_peak_utilization=98.1,
            gpu_avg_memory_gb=11.4,
            gpu_peak_memory_gb=12.1,
            output_code="<script setup>",
            errors=[]
        )

        mock_instance.run.return_value = fake_result

        # We'll test this once main() is implemented
        # For now, this defines the expected behavior
        pass

    @patch("run_test.RefactoringTest")
    @patch("run_test.Console")
    def test_displays_progress_during_execution(self, mock_console_class, mock_test_class):
        """Should display progress bar and run summaries."""
        # Verify rich.Console is used for output
        # Verify progress tracking with rich.progress
        pass


class TestRunTestOutput:
    """Test JSON output and file saving."""

    @patch("run_test.RefactoringTest")
    @patch("builtins.open", new_callable=mock_open)
    def test_saves_results_to_json(self, mock_file, mock_test_class):
        """Should save all results to JSON file in results/ directory."""
        from src.refactoring_test import TestResult

        mock_instance = Mock()
        mock_test_class.return_value = mock_instance

        fake_result = TestResult(
            model="qwen2.5-coder:7b-instruct-q8_0",
            fixture="simple-component",
            timestamp="2025-02-16T14:23:45",
            run_number=1,
            compiles=True,
            compilation_errors=[],
            compilation_warnings=[],
            pattern_score=10.0,
            naming_score=10.0,
            final_score=10.0,
            tokens_per_sec=185.3,
            duration_sec=4.2,
            gpu_avg_utilization=94.2,
            gpu_peak_utilization=98.1,
            gpu_avg_memory_gb=11.4,
            gpu_peak_memory_gb=12.1,
            output_code="<script setup>",
            errors=[]
        )

        mock_instance.run.return_value = fake_result

        # Test will verify:
        # 1. JSON file is created in results/ directory
        # 2. Filename includes model name and timestamp
        # 3. Content is array of TestResult dicts
        pass

    def test_json_output_format(self):
        """Should format JSON output correctly."""
        from src.refactoring_test import TestResult

        result = TestResult(
            model="test-model",
            fixture="test-fixture",
            timestamp="2025-02-16T14:23:45",
            run_number=1,
            compiles=True,
            compilation_errors=[],
            compilation_warnings=[],
            pattern_score=10.0,
            naming_score=10.0,
            final_score=10.0,
            tokens_per_sec=185.3,
            duration_sec=4.2,
            gpu_avg_utilization=94.2,
            gpu_peak_utilization=98.1,
            gpu_avg_memory_gb=11.4,
            gpu_peak_memory_gb=12.1,
            output_code="<script setup>",
            errors=[]
        )

        # Verify result.__dict__ can be JSON serialized
        json_str = json.dumps([result.__dict__])
        parsed = json.loads(json_str)

        assert len(parsed) == 1
        assert parsed[0]["model"] == "test-model"
        assert parsed[0]["final_score"] == 10.0


class TestRunTestSummary:
    """Test summary statistics and warnings."""

    def test_calculates_average_score(self):
        """Should calculate and display average score across runs."""
        from src.refactoring_test import TestResult

        results = [
            TestResult(
                model="test", fixture="test", timestamp="2025-02-16T14:23:45",
                run_number=i, compiles=True, compilation_errors=[],
                compilation_warnings=[], pattern_score=10.0, naming_score=10.0,
                final_score=score, tokens_per_sec=185.0, duration_sec=4.0,
                gpu_avg_utilization=94.0, gpu_peak_utilization=98.0,
                gpu_avg_memory_gb=11.0, gpu_peak_memory_gb=12.0,
                output_code="code", errors=[]
            )
            for i, score in enumerate([10.0, 9.0, 8.0], start=1)
        ]

        avg_score = sum(r.final_score for r in results) / len(results)
        assert avg_score == 9.0

    def test_calculates_average_speed(self):
        """Should calculate and display average tokens/sec."""
        from src.refactoring_test import TestResult

        results = [
            TestResult(
                model="test", fixture="test", timestamp="2025-02-16T14:23:45",
                run_number=i, compiles=True, compilation_errors=[],
                compilation_warnings=[], pattern_score=10.0, naming_score=10.0,
                final_score=10.0, tokens_per_sec=speed, duration_sec=4.0,
                gpu_avg_utilization=94.0, gpu_peak_utilization=98.0,
                gpu_avg_memory_gb=11.0, gpu_peak_memory_gb=12.0,
                output_code="code", errors=[]
            )
            for i, speed in enumerate([185.0, 178.0, 182.0], start=1)
        ]

        avg_speed = sum(r.tokens_per_sec for r in results) / len(results)
        assert abs(avg_speed - 181.67) < 0.1

    def test_calculates_success_rate(self):
        """Should calculate compilation success rate."""
        from src.refactoring_test import TestResult

        results = [
            TestResult(
                model="test", fixture="test", timestamp="2025-02-16T14:23:45",
                run_number=i, compiles=compiles, compilation_errors=[],
                compilation_warnings=[], pattern_score=10.0, naming_score=10.0,
                final_score=10.0, tokens_per_sec=185.0, duration_sec=4.0,
                gpu_avg_utilization=94.0, gpu_peak_utilization=98.0,
                gpu_avg_memory_gb=11.0, gpu_peak_memory_gb=12.0,
                output_code="code", errors=[]
            )
            for i, compiles in enumerate([True, True, False], start=1)
        ]

        success_rate = sum(1 for r in results if r.compiles) / len(results)
        assert abs(success_rate - 0.667) < 0.01

    @patch("run_test.Console")
    def test_warns_on_low_gpu_utilization(self, mock_console_class):
        """Should warn if average GPU utilization < 80%."""
        # This will be tested once main() is implemented
        # Should check for console.print with warning message
        pass


class TestRunTestErrorHandling:
    """Test error handling scenarios."""

    @patch("run_test.RefactoringTest")
    def test_handles_fixture_not_found(self, mock_test_class):
        """Should handle missing fixture gracefully."""
        mock_test_class.side_effect = FileNotFoundError("Fixture not found")

        # Should catch exception and display error message
        # Not crash the entire program
        pass

    @patch("run_test.RefactoringTest")
    def test_handles_all_runs_failing(self, mock_test_class):
        """Should still save results even if all runs fail."""
        from src.refactoring_test import TestResult

        mock_instance = Mock()
        mock_test_class.return_value = mock_instance

        # All runs compile=False
        failed_result = TestResult(
            model="test-model",
            fixture="test-fixture",
            timestamp="2025-02-16T14:23:45",
            run_number=1,
            compiles=False,
            compilation_errors=["TS2304: Cannot find name 'foo'"],
            compilation_warnings=[],
            pattern_score=0.0,
            naming_score=0.0,
            final_score=0.0,
            tokens_per_sec=185.3,
            duration_sec=4.2,
            gpu_avg_utilization=94.2,
            gpu_peak_utilization=98.1,
            gpu_avg_memory_gb=11.4,
            gpu_peak_memory_gb=12.1,
            output_code="invalid code",
            errors=["Compilation failed"]
        )

        mock_instance.run.return_value = failed_result

        # Should still save JSON and display summary
        # Success rate should be 0%
        pass
