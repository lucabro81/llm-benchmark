"""Tests for run_test.py CLI runner."""

import json
from pathlib import Path

import pytest

from src.refactoring.simple_component.test_runner import BenchmarkResult
from run_test import discover_fixtures


def _make_result(run_number=1, final_score=10.0, tokens_per_sec=185.0, compiles=True):
    return BenchmarkResult(
        model="test", fixture="test", timestamp="2025-01-17T14:23:45",
        run_number=run_number, compiles=compiles, compilation_errors=[],
        compilation_warnings=[], pattern_score=10.0, ast_missing=[],
        ast_checks={}, naming_score=10.0, naming_violations=[],
        final_score=final_score,
        scoring_weights={"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
        tokens_per_sec=tokens_per_sec, duration_sec=4.0,
        output_code="code", errors=[],
    )


class TestRunTestSummary:
    """Test summary statistics computed over multiple runs."""

    def test_average_score(self):
        """Should compute correct mean final_score across runs."""
        results = [_make_result(final_score=s) for s in [10.0, 9.0, 8.0]]
        avg = sum(r.final_score for r in results) / len(results)
        assert avg == 9.0

    def test_average_speed(self):
        """Should compute correct mean tokens/sec across runs."""
        results = [_make_result(tokens_per_sec=s) for s in [185.0, 178.0, 182.0]]
        avg = sum(r.tokens_per_sec for r in results) / len(results)
        assert abs(avg - 181.67) < 0.1

    def test_compilation_success_rate(self):
        """Should compute correct fraction of runs that compiled."""
        results = [_make_result(compiles=c) for c in [True, True, False]]
        rate = sum(1 for r in results if r.compiles) / len(results)
        assert abs(rate - 0.667) < 0.01


class TestDiscoverFixtures:
    """Test fixture discovery from filesystem."""

    def test_discovers_valid_fixtures(self, tmp_path):
        """Should return fixture dirs that contain validation_spec.json."""
        (tmp_path / "fixture-a").mkdir()
        (tmp_path / "fixture-a" / "validation_spec.json").write_text("{}")
        (tmp_path / "fixture-b").mkdir()
        (tmp_path / "fixture-b" / "validation_spec.json").write_text("{}")

        result = discover_fixtures(tmp_path)
        assert len(result) == 2
        assert all(p.name.startswith("fixture-") for p in result)

    def test_ignores_dirs_without_validation_spec(self, tmp_path):
        """Should skip dirs that lack validation_spec.json."""
        (tmp_path / "valid-fixture").mkdir()
        (tmp_path / "valid-fixture" / "validation_spec.json").write_text("{}")
        (tmp_path / "no-spec-dir").mkdir()  # no validation_spec.json

        result = discover_fixtures(tmp_path)
        assert len(result) == 1
        assert result[0].name == "valid-fixture"

    def test_returns_sorted_by_name(self, tmp_path):
        """Should return fixtures in alphabetical order."""
        for name in ["z-fixture", "a-fixture", "m-fixture"]:
            (tmp_path / name).mkdir()
            (tmp_path / name / "validation_spec.json").write_text("{}")

        result = discover_fixtures(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_raises_if_base_dir_missing(self, tmp_path):
        """Should raise FileNotFoundError if the base directory does not exist."""
        with pytest.raises(FileNotFoundError):
            discover_fixtures(tmp_path / "nonexistent")

    def test_raises_if_no_valid_fixtures(self, tmp_path):
        """Should raise FileNotFoundError if base_dir has no valid fixtures."""
        (tmp_path / "empty-dir").mkdir()  # dir but no validation_spec.json
        with pytest.raises(FileNotFoundError):
            discover_fixtures(tmp_path)


class TestRunTestOutput:
    """Test JSON serialisation of results."""

    def test_result_serialises_to_json(self):
        """BenchmarkResult.__dict__ should be JSON-serialisable with correct values."""
        result = _make_result(run_number=1, final_score=10.0)
        parsed = json.loads(json.dumps([result.__dict__]))

        assert len(parsed) == 1
        assert parsed[0]["model"] == "test"
        assert parsed[0]["final_score"] == 10.0
        assert parsed[0]["run_number"] == 1
