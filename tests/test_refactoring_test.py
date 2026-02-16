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
