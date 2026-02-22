"""Tests for RefactoringTest orchestrator."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.refactoring_test import RefactoringTest, TestResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fixture(tmp_path, scoring=None):
    """Create a minimal valid fixture directory."""
    fixture_path = tmp_path / "test-fixture"
    fixture_path.mkdir()

    (fixture_path / "prompt.md").write_text("Refactor: {{original_code}}")

    spec = {
        "target_file": "src/test.vue",
        "required_patterns": {"interfaces": ["TestProps"]},
        "naming_conventions": {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
        "scoring": scoring or {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
    }
    (fixture_path / "validation_spec.json").write_text(json.dumps(spec))

    target_project = fixture_path / "target_project"
    target_project.mkdir()
    src_dir = target_project / "src"
    src_dir.mkdir()
    (src_dir / "test.vue").write_text("<script setup>\nconst props = defineProps({ title: String })\n</script>")

    return fixture_path


def _gpu_side_effect(metrics):
    """Return a side_effect that executes the callback before returning metrics."""
    def _run(callback, **kwargs):
        callback()
        return metrics
    return _run


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

class TestRefactoringTestInit:
    """Test fixture loading on __init__."""

    def test_loads_prompt_and_spec(self, tmp_path):
        """Should load prompt template and validation spec from fixture dir."""
        fixture_path = _make_fixture(tmp_path)
        test = RefactoringTest(model="test-model", fixture_path=fixture_path)

        assert "{{original_code}}" in test.prompt_template
        assert test.validation_spec["target_file"] == "src/test.vue"
        assert test.original_code == "<script setup>\nconst props = defineProps({ title: String })\n</script>"
        assert test.fixture_name == "test-fixture"

    def test_raises_on_missing_prompt(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        with pytest.raises(FileNotFoundError, match="prompt.md"):
            RefactoringTest(model="test-model", fixture_path=fixture_path)

    def test_raises_on_missing_validation_spec(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("test")
        with pytest.raises(FileNotFoundError, match="validation_spec.json"):
            RefactoringTest(model="test-model", fixture_path=fixture_path)

    def test_raises_on_missing_target_project(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("test")
        (fixture_path / "validation_spec.json").write_text('{"target_file": "test.vue"}')
        with pytest.raises(FileNotFoundError, match="target_project"):
            RefactoringTest(model="test-model", fixture_path=fixture_path)


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

class TestRefactoringTestRun:
    """Test run() — scoring calculation and file lifecycle."""

    @patch("src.refactoring_test.ollama_client")
    @patch("src.refactoring_test.gpu_monitor")
    @patch("src.refactoring_test.validator")
    def test_perfect_score_when_all_checks_pass(self, mock_validator, mock_gpu, mock_ollama, tmp_path):
        """Should produce final_score=10.0 when compilation=OK, pattern=10, naming=1."""
        from src.ollama_client import ChatResult
        from src.gpu_monitor import GPUMetrics
        from src.validator import CompilationResult, ASTResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text='<script setup lang="ts">\ninterface TestProps { title: string }\nconst props = defineProps<TestProps>()\n</script>',
            duration_sec=4.2, tokens_generated=50, tokens_per_sec=185.3, success=True,
        )
        mock_gpu.monitor_gpu_during_inference.side_effect = _gpu_side_effect(
            GPUMetrics(avg_utilization=94.2, peak_utilization=98.1, avg_memory_used=11.4, peak_memory_used=12.1, samples=10)
        )
        mock_validator.validate_compilation.return_value = CompilationResult(success=True, errors=[], warnings=[], duration_sec=2.0)
        mock_validator.validate_ast_structure.return_value = ASTResult(has_interfaces=True, has_type_annotations=True, has_imports=False, missing=[], score=10.0)
        mock_validator.validate_naming.return_value = NamingResult(follows_conventions=True, violations=[], score=1.0)

        result = RefactoringTest(model="test-model", fixture_path=_make_fixture(tmp_path)).run(run_number=1)

        assert result.final_score == 10.0
        assert result.compiles is True
        assert result.tokens_per_sec == 185.3
        assert result.gpu_avg_utilization == 94.2

    @patch("src.refactoring_test.ollama_client")
    @patch("src.refactoring_test.gpu_monitor")
    @patch("src.refactoring_test.validator")
    def test_weighted_scoring_calculation(self, mock_validator, mock_gpu, mock_ollama, tmp_path):
        """Compilation=1*0.5 + pattern=0.6*0.4 + naming=1*0.1 → 8.4."""
        from src.ollama_client import ChatResult
        from src.gpu_monitor import GPUMetrics
        from src.validator import CompilationResult, ASTResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="code", duration_sec=4.0, tokens_generated=50, tokens_per_sec=150.0, success=True,
        )
        mock_gpu.monitor_gpu_during_inference.side_effect = _gpu_side_effect(
            GPUMetrics(avg_utilization=90.0, peak_utilization=95.0, avg_memory_used=10.0, peak_memory_used=11.0, samples=5)
        )
        mock_validator.validate_compilation.return_value = CompilationResult(success=True, errors=[], warnings=[], duration_sec=2.0)
        mock_validator.validate_ast_structure.return_value = ASTResult(
            has_interfaces=True, has_type_annotations=False, has_imports=False, missing=["type_annotations"], score=6.0
        )
        mock_validator.validate_naming.return_value = NamingResult(follows_conventions=True, violations=[], score=1.0)

        result = RefactoringTest(model="test-model", fixture_path=_make_fixture(tmp_path)).run(run_number=1)

        # (1.0*0.5 + 0.6*0.4 + 1.0*0.1) * 10 = 8.4
        assert result.pattern_score == 6.0
        assert result.naming_score == 10.0  # naming_result.score (0-1) scaled to 0-10
        assert abs(result.final_score - 8.4) < 0.1

    @patch("src.refactoring_test.ollama_client")
    @patch("src.refactoring_test.gpu_monitor")
    @patch("src.refactoring_test.validator")
    def test_compilation_failure_caps_score(self, mock_validator, mock_gpu, mock_ollama, tmp_path):
        """Compilation=0*0.5 + pattern=1*0.4 + naming=1*0.1 → 5.0."""
        from src.ollama_client import ChatResult
        from src.gpu_monitor import GPUMetrics
        from src.validator import CompilationResult, ASTResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="bad code", duration_sec=3.0, tokens_generated=30, tokens_per_sec=100.0, success=True,
        )
        mock_gpu.monitor_gpu_during_inference.side_effect = _gpu_side_effect(
            GPUMetrics(avg_utilization=80.0, peak_utilization=85.0, avg_memory_used=9.0, peak_memory_used=10.0, samples=3)
        )
        mock_validator.validate_compilation.return_value = CompilationResult(
            success=False, errors=["TS2304: Cannot find name 'foo'"], warnings=[], duration_sec=1.0
        )
        mock_validator.validate_ast_structure.return_value = ASTResult(
            has_interfaces=True, has_type_annotations=True, has_imports=False, missing=[], score=10.0
        )
        mock_validator.validate_naming.return_value = NamingResult(follows_conventions=True, violations=[], score=1.0)

        result = RefactoringTest(model="test-model", fixture_path=_make_fixture(tmp_path)).run(run_number=1)

        # (0*0.5 + 1.0*0.4 + 1.0*0.1) * 10 = 5.0
        assert result.compiles is False
        assert abs(result.final_score - 5.0) < 0.1

    @patch("src.refactoring_test.ollama_client")
    @patch("src.refactoring_test.gpu_monitor")
    @patch("src.refactoring_test.validator")
    def test_original_file_restored_after_run(self, mock_validator, mock_gpu, mock_ollama, tmp_path):
        """Target file must be restored to original content after run completes."""
        from src.ollama_client import ChatResult
        from src.gpu_monitor import GPUMetrics
        from src.validator import CompilationResult, ASTResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="MODIFIED CODE", duration_sec=4.0, tokens_generated=50, tokens_per_sec=150.0, success=True,
        )
        mock_gpu.monitor_gpu_during_inference.side_effect = _gpu_side_effect(
            GPUMetrics(avg_utilization=90.0, peak_utilization=95.0, avg_memory_used=10.0, peak_memory_used=11.0, samples=5)
        )
        mock_validator.validate_compilation.return_value = CompilationResult(success=True, errors=[], warnings=[], duration_sec=1.0)
        mock_validator.validate_ast_structure.return_value = ASTResult(has_interfaces=True, has_type_annotations=True, has_imports=False, missing=[], score=10.0)
        mock_validator.validate_naming.return_value = NamingResult(follows_conventions=True, violations=[], score=1.0)

        test = RefactoringTest(model="test-model", fixture_path=_make_fixture(tmp_path))
        original_code = test.original_code

        test.run(run_number=1)

        assert test.target_file.read_text() == original_code
