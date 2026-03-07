"""Tests for run_test.py — CLI entry point.

Coverage focus: discover_fixtures, _get_runner_module, _get_runner_class,
save_results, parse_arguments.

These tests prevent regressions like the FIXTURES_BASE → TASKS_DIR bug where
the default parameter of discover_fixtures referenced a deleted constant.
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from run_test import (
    TASKS_DIR,
    _RUNNER_MAP,
    _get_runner_class,
    _get_runner_module,
    discover_fixtures,
    parse_arguments,
    save_results,
)
from src.creation.nuxt_form_oneshot.test_runner import BenchmarkResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fixture(base: Path, name: str) -> Path:
    """Create a valid fixture directory (has validation_spec.json)."""
    d = base / name
    d.mkdir(parents=True)
    (d / "validation_spec.json").write_text("{}")
    return d


def make_result(**kwargs) -> BenchmarkResult:
    defaults = dict(
        model="mymodel",
        fixture="my-fixture",
        timestamp="2024-01-01T00:00:00",
        run_number=1,
        compiles=True,
        compilation_errors=[],
        compilation_warnings=[],
        pattern_score=8.0,
        ast_missing=[],
        ast_checks={},
        naming_score=1.0,
        naming_violations=[],
        final_score=7.0,
        scoring_weights={},
        tokens_per_sec=50.0,
        duration_sec=10.0,
        output_code="",
        errors=[],
    )
    defaults.update(kwargs)
    return BenchmarkResult(**defaults)


# ---------------------------------------------------------------------------
# discover_fixtures
# ---------------------------------------------------------------------------

class TestDiscoverFixtures:
    def test_discovers_valid_fixtures(self, tmp_path):
        make_fixture(tmp_path, "alpha")
        make_fixture(tmp_path, "beta")
        result = discover_fixtures(tmp_path)
        assert len(result) == 2
        assert all(isinstance(p, Path) for p in result)

    def test_ignores_dirs_without_spec(self, tmp_path):
        make_fixture(tmp_path, "valid")
        (tmp_path / "no-spec").mkdir()
        result = discover_fixtures(tmp_path)
        assert len(result) == 1
        assert result[0].name == "valid"

    def test_returns_sorted_by_name(self, tmp_path):
        make_fixture(tmp_path, "zebra")
        make_fixture(tmp_path, "alpha")
        make_fixture(tmp_path, "middle")
        result = discover_fixtures(tmp_path)
        assert [p.name for p in result] == ["alpha", "middle", "zebra"]

    def test_raises_if_base_dir_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            discover_fixtures(tmp_path / "does-not-exist")

    def test_raises_if_no_valid_fixtures(self, tmp_path):
        (tmp_path / "empty-dir").mkdir()
        with pytest.raises(FileNotFoundError):
            discover_fixtures(tmp_path)

    def test_default_parameter_is_tasks_dir(self):
        """Regression: default param must be TASKS_DIR, not a deleted constant."""
        import inspect
        sig = inspect.signature(discover_fixtures)
        default = sig.parameters["base_dir"].default
        assert default == TASKS_DIR, (
            f"discover_fixtures default is {default!r}, expected TASKS_DIR={TASKS_DIR!r}. "
            "Likely regression: deleted constant used as default."
        )


# ---------------------------------------------------------------------------
# _get_runner_module
# ---------------------------------------------------------------------------

class TestGetRunnerModule:
    def test_raises_for_unregistered_fixture(self, tmp_path):
        fixture = tmp_path / "unknown-task"
        fixture.mkdir()
        with pytest.raises(ValueError, match="No runner registered"):
            _get_runner_module(fixture)

    def test_error_message_includes_fixture_name(self, tmp_path):
        fixture = tmp_path / "my-unknown-task"
        fixture.mkdir()
        with pytest.raises(ValueError, match="my-unknown-task"):
            _get_runner_module(fixture)

    def test_returns_module_for_known_fixture(self, tmp_path):
        fixture = tmp_path / "nuxt-form-oneshot"
        fixture.mkdir()
        module = _get_runner_module(fixture)
        assert hasattr(module, "CreationTest")

    def test_all_five_tasks_registered(self):
        expected = {
            "nuxt-form-oneshot",
            "nuxt-form-agent-guided",
            "nuxt-form-agent-twofiles",
            "nuxt-form-agent-rag",
            "nuxt-form-agent-full",
        }
        assert expected == set(_RUNNER_MAP.keys())

    def test_runner_map_module_paths_are_importable(self):
        import importlib
        for fixture_name, module_path in _RUNNER_MAP.items():
            mod = importlib.import_module(module_path)
            assert mod is not None, f"Cannot import {module_path} for {fixture_name}"


# ---------------------------------------------------------------------------
# _get_runner_class
# ---------------------------------------------------------------------------

class TestGetRunnerClass:
    def test_returns_agent_test_if_present(self):
        class AgentTest: pass
        class CreationTest: pass
        mod = types.SimpleNamespace(AgentTest=AgentTest, CreationTest=CreationTest)
        assert _get_runner_class(mod) is AgentTest

    def test_returns_creation_test_as_fallback(self):
        class CreationTest: pass
        mod = types.SimpleNamespace(CreationTest=CreationTest)
        assert _get_runner_class(mod) is CreationTest

    def test_prefers_agent_over_creation(self):
        class AgentTest: pass
        class CreationTest: pass
        mod = types.SimpleNamespace(AgentTest=AgentTest, CreationTest=CreationTest)
        assert _get_runner_class(mod) is AgentTest


# ---------------------------------------------------------------------------
# save_results
# ---------------------------------------------------------------------------

class TestSaveResults:
    def test_creates_output_dir(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path / "new-results")
        result = make_result()
        save_results([result], "mymodel", "my-fixture")
        assert (tmp_path / "new-results").exists()

    def test_filename_contains_fixture_and_model(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        result = make_result(timestamp="2024-01-01T12:00:00")
        path = save_results([result], "mymodel:7b", "my-fixture")
        assert "my-fixture" in path.name
        assert "mymodel" in path.name

    def test_model_colon_replaced_in_filename(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        result = make_result()
        path = save_results([result], "model:7b", "fix")
        assert ":" not in path.name

    def test_output_is_valid_json(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = [make_result(run_number=1), make_result(run_number=2)]
        path = save_results(results, "model", "fixture")
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == 2

    def test_result_fields_serialized(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        result = make_result(final_score=9.5)
        path = save_results([result], "model", "fixture")
        data = json.loads(path.read_text())
        assert data[0]["final_score"] == 9.5


# ---------------------------------------------------------------------------
# parse_arguments
# ---------------------------------------------------------------------------

class TestParseArguments:
    def test_model_required(self):
        with patch("sys.argv", ["run_test.py"]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_fixture_optional(self):
        with patch("sys.argv", ["run_test.py", "--model", "mymodel"]):
            args = parse_arguments()
        assert args.fixture is None

    def test_runs_default_3(self):
        with patch("sys.argv", ["run_test.py", "--model", "mymodel"]):
            args = parse_arguments()
        assert args.runs == 3

    def test_runs_custom(self):
        with patch("sys.argv", ["run_test.py", "--model", "mymodel", "--runs", "5"]):
            args = parse_arguments()
        assert args.runs == 5

    def test_fixture_passed(self):
        with patch("sys.argv", ["run_test.py", "--model", "mymodel", "--fixture", "nuxt-form-oneshot"]):
            args = parse_arguments()
        assert args.fixture == "nuxt-form-oneshot"
