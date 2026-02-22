"""Tests for RefactoringTest orchestrator following TDD approach.

This test suite validates the refactoring test orchestration workflow,
including fixture loading, LLM integration, validation, and scoring.
"""

import json
from dataclasses import is_dataclass
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from src.refactoring_test import (
    TestResult,
    RefactoringTest,
)


class TestResultDataclass:
    """Test TestResult dataclass structure and properties."""

    def test_test_result_is_dataclass(self):
        """TestResult should be a dataclass."""
        assert is_dataclass(TestResult)

    def test_test_result_complete_data(self):
        """TestResult should store all test execution data."""
        result = TestResult(
            model="qwen2.5-coder:7b-instruct-q8_0",
            fixture="simple-component",
            timestamp="2025-02-16T14:23:45",
            run_number=1,
            compiles=True,
            compilation_errors=[],
            compilation_warnings=[],
            pattern_score=4.0,
            naming_score=1.0,
            final_score=10.0,
            tokens_per_sec=185.3,
            duration_sec=4.2,
            gpu_avg_utilization=94.2,
            gpu_peak_utilization=98.1,
            gpu_avg_memory_gb=11.4,
            gpu_peak_memory_gb=12.1,
            output_code="<script setup lang=\"ts\">...",
            errors=[],
        )

        assert result.model == "qwen2.5-coder:7b-instruct-q8_0"
        assert result.fixture == "simple-component"
        assert result.compiles is True
        assert result.final_score == 10.0
        assert result.tokens_per_sec == 185.3
        assert result.gpu_avg_utilization == 94.2

    def test_test_result_with_errors(self):
        """TestResult should track compilation and validation errors."""
        result = TestResult(
            model="test-model",
            fixture="test-fixture",
            timestamp="2025-02-16T14:23:45",
            run_number=1,
            compiles=False,
            compilation_errors=["TS2304: Cannot find name 'foo'"],
            compilation_warnings=["Unused variable"],
            pattern_score=0.0,
            naming_score=0.0,
            final_score=0.0,
            tokens_per_sec=150.0,
            duration_sec=3.0,
            gpu_avg_utilization=85.0,
            gpu_peak_utilization=90.0,
            gpu_avg_memory_gb=10.0,
            gpu_peak_memory_gb=11.0,
            output_code="invalid code",
            errors=["Model timeout"],
        )

        assert result.compiles is False
        assert len(result.compilation_errors) == 1
        assert result.final_score == 0.0
        assert len(result.errors) == 1


class TestRefactoringTestInit:
    """Test RefactoringTest initialization and fixture loading."""

    def test_init_loads_fixture_files(self, tmp_path):
        """Should load prompt.md and validation_spec.json on init."""
        # Create fixture structure
        fixture_path = tmp_path / "test-fixture"
        fixture_path.mkdir()

        # Create prompt.md
        prompt_content = "Refactor this: {{original_code}}"
        (fixture_path / "prompt.md").write_text(prompt_content)

        # Create validation_spec.json
        validation_spec = {
            "target_file": "src/components/Test.vue",
            "required_patterns": {
                "interfaces": ["TestProps"],
                "type_annotations": ["defineProps<TestProps>"],
                "script_lang": "ts"
            },
            "naming_conventions": {
                "interfaces": "PascalCase",
                "props_interface_suffix": "Props"
            },
            "scoring": {
                "compilation": 0.5,
                "pattern_match": 0.4,
                "naming": 0.1
            }
        }
        (fixture_path / "validation_spec.json").write_text(json.dumps(validation_spec))

        # Create target_project structure
        target_project = fixture_path / "target_project"
        target_project.mkdir()
        src_dir = target_project / "src" / "components"
        src_dir.mkdir(parents=True)

        original_code = "<script setup>\nconst props = defineProps({ title: String })\n</script>"
        (src_dir / "Test.vue").write_text(original_code)

        # Initialize RefactoringTest
        test = RefactoringTest(
            model="test-model",
            fixture_path=fixture_path
        )

        assert test.model == "test-model"
        assert test.fixture_path == fixture_path
        assert "{{original_code}}" in test.prompt_template
        assert test.validation_spec["target_file"] == "src/components/Test.vue"
        assert test.original_code == original_code
        assert test.target_file.name == "Test.vue"

    def test_init_raises_on_missing_prompt(self, tmp_path):
        """Should raise FileNotFoundError if prompt.md missing."""
        fixture_path = tmp_path / "incomplete-fixture"
        fixture_path.mkdir()

        with pytest.raises(FileNotFoundError, match="prompt.md"):
            RefactoringTest(model="test-model", fixture_path=fixture_path)

    def test_init_raises_on_missing_validation_spec(self, tmp_path):
        """Should raise FileNotFoundError if validation_spec.json missing."""
        fixture_path = tmp_path / "incomplete-fixture"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("test")

        with pytest.raises(FileNotFoundError, match="validation_spec.json"):
            RefactoringTest(model="test-model", fixture_path=fixture_path)

    def test_init_raises_on_missing_target_project(self, tmp_path):
        """Should raise FileNotFoundError if target_project missing."""
        fixture_path = tmp_path / "incomplete-fixture"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("test")
        (fixture_path / "validation_spec.json").write_text('{"target_file": "test.vue"}')

        with pytest.raises(FileNotFoundError, match="target_project"):
            RefactoringTest(model="test-model", fixture_path=fixture_path)

    def test_init_stores_fixture_name(self, tmp_path):
        """Should extract fixture name from path."""
        fixture_path = tmp_path / "my-fixture"
        fixture_path.mkdir()

        (fixture_path / "prompt.md").write_text("test")
        (fixture_path / "validation_spec.json").write_text(
            '{"target_file": "src/test.vue", "scoring": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1}}'
        )

        target_project = fixture_path / "target_project"
        target_project.mkdir()
        src_dir = target_project / "src"
        src_dir.mkdir()
        (src_dir / "test.vue").write_text("test")

        test = RefactoringTest(model="test-model", fixture_path=fixture_path)

        assert test.fixture_name == "my-fixture"


class TestRefactoringTestRun:
    """Test RefactoringTest.run() workflow (Phase 1 prompt-only)."""

    @patch("src.refactoring_test.ollama_client")
    @patch("src.refactoring_test.gpu_monitor")
    @patch("src.refactoring_test.validator")
    def test_successful_run_workflow(self, mock_validator, mock_gpu, mock_ollama, tmp_path):
        """Should execute complete workflow and return TestResult."""
        # Setup fixture
        fixture_path = self._create_test_fixture(tmp_path)

        # Mock dependencies
        from src.ollama_client import ChatResult
        from src.gpu_monitor import GPUMetrics
        from src.validator import CompilationResult, ASTResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text='<script setup lang="ts">\ninterface TestProps { title: string }\nconst props = defineProps<TestProps>()\n</script>',
            duration_sec=4.2,
            tokens_generated=50,
            tokens_per_sec=185.3,
            success=True,
            error=None
        )

        gpu_metrics = GPUMetrics(
            avg_utilization=94.2,
            peak_utilization=98.1,
            avg_memory_used=11.4,
            peak_memory_used=12.1,
            samples=10
        )

        def run_callback_and_return_metrics(callback, **kwargs):
            callback()
            return gpu_metrics

        mock_gpu.monitor_gpu_during_inference.side_effect = run_callback_and_return_metrics

        mock_validator.validate_compilation.return_value = CompilationResult(
            success=True,
            errors=[],
            warnings=[],
            duration_sec=2.0
        )

        mock_validator.validate_ast_structure.return_value = ASTResult(
            has_interfaces=True,
            has_type_annotations=True,
            has_imports=False,
            missing=[],
            score=10.0
        )

        mock_validator.validate_naming.return_value = NamingResult(
            follows_conventions=True,
            violations=[],
            score=1.0
        )

        # Run test
        test = RefactoringTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        # Verify TestResult
        assert isinstance(result, TestResult)
        assert result.model == "test-model"
        assert result.fixture == fixture_path.name
        assert result.run_number == 1
        assert result.compiles is True
        assert result.final_score == 10.0
        assert result.tokens_per_sec == 185.3
        assert result.gpu_avg_utilization == 94.2

        # Verify components called
        mock_ollama.chat.assert_called_once()
        mock_validator.validate_compilation.assert_called_once()
        mock_validator.validate_ast_structure.assert_called_once()
        mock_validator.validate_naming.assert_called_once()

    @patch("src.refactoring_test.ollama_client")
    @patch("src.refactoring_test.gpu_monitor")
    @patch("src.refactoring_test.validator")
    def test_weighted_scoring_calculation(self, mock_validator, mock_gpu, mock_ollama, tmp_path):
        """Should calculate weighted final score correctly."""
        fixture_path = self._create_test_fixture(tmp_path)

        from src.ollama_client import ChatResult
        from src.gpu_monitor import GPUMetrics
        from src.validator import CompilationResult, ASTResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="code",
            duration_sec=4.0,
            tokens_generated=50,
            tokens_per_sec=150.0,
            success=True,
        )

        gpu_metrics_weighted = GPUMetrics(
            avg_utilization=90.0, peak_utilization=95.0,
            avg_memory_used=10.0, peak_memory_used=11.0, samples=5
        )

        def run_callback_and_return_metrics_weighted(callback, **kwargs):
            callback()
            return gpu_metrics_weighted

        mock_gpu.monitor_gpu_during_inference.side_effect = run_callback_and_return_metrics_weighted

        # Compilation: success (1.0) * 0.5 = 0.5
        # Pattern: 6.0/10 = 0.6 * 0.4 = 0.24
        # Naming: 1.0 * 0.1 = 0.1
        # Total: (0.5 + 0.24 + 0.1) * 10 = 8.4
        mock_validator.validate_compilation.return_value = CompilationResult(
            success=True, errors=[], warnings=[], duration_sec=2.0
        )
        mock_validator.validate_ast_structure.return_value = ASTResult(
            has_interfaces=True, has_type_annotations=False,
            has_imports=False, missing=["type_annotations"], score=6.0
        )
        mock_validator.validate_naming.return_value = NamingResult(
            follows_conventions=True, violations=[], score=1.0
        )

        test = RefactoringTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        # Check weighted score
        assert result.pattern_score == 6.0
        assert result.naming_score == 1.0
        assert abs(result.final_score - 8.4) < 0.1

    @patch("src.refactoring_test.ollama_client")
    @patch("src.refactoring_test.gpu_monitor")
    @patch("src.refactoring_test.validator")
    def test_restores_original_file_after_run(self, mock_validator, mock_gpu, mock_ollama, tmp_path):
        """Should restore original file content after test completes."""
        fixture_path = self._create_test_fixture(tmp_path)

        from src.ollama_client import ChatResult
        from src.gpu_monitor import GPUMetrics
        from src.validator import CompilationResult, ASTResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="MODIFIED CODE",
            duration_sec=4.0, tokens_generated=50, tokens_per_sec=150.0, success=True
        )
        gpu_metrics_restore = GPUMetrics(
            avg_utilization=90.0, peak_utilization=95.0,
            avg_memory_used=10.0, peak_memory_used=11.0, samples=5
        )

        def run_callback_and_return_metrics_restore(callback, **kwargs):
            callback()
            return gpu_metrics_restore

        mock_gpu.monitor_gpu_during_inference.side_effect = run_callback_and_return_metrics_restore
        mock_validator.validate_compilation.return_value = CompilationResult(
            success=True, errors=[], warnings=[], duration_sec=1.0
        )
        mock_validator.validate_ast_structure.return_value = ASTResult(
            has_interfaces=True, has_type_annotations=True, has_imports=False,
            missing=[], score=10.0
        )
        mock_validator.validate_naming.return_value = NamingResult(
            follows_conventions=True, violations=[], score=1.0
        )

        test = RefactoringTest(model="test-model", fixture_path=fixture_path)
        original_code = test.original_code

        # Run test
        test.run(run_number=1)

        # Verify file restored
        restored_code = test.target_file.read_text()
        assert restored_code == original_code

    def _create_test_fixture(self, tmp_path):
        """Helper to create minimal test fixture."""
        fixture_path = tmp_path / "test-fixture"
        fixture_path.mkdir()

        (fixture_path / "prompt.md").write_text("Refactor: {{original_code}}")

        validation_spec = {
            "target_file": "src/test.vue",
            "required_patterns": {"interfaces": ["TestProps"]},
            "naming_conventions": {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
            "scoring": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1}
        }
        (fixture_path / "validation_spec.json").write_text(json.dumps(validation_spec))

        target_project = fixture_path / "target_project"
        target_project.mkdir()
        src_dir = target_project / "src"
        src_dir.mkdir()
        (src_dir / "test.vue").write_text("<script setup>\nconst props = defineProps({ title: String })\n</script>")

        return fixture_path
