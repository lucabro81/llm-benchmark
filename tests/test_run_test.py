"""Tests for run_test.py — CLI entry point.

Coverage focus: discover_fixtures, _get_runner_module, _get_runner_class,
save_results, parse_arguments.

These tests prevent regressions like the FIXTURES_BASE → TASKS_DIR bug where
the default parameter of discover_fixtures referenced a deleted constant.
"""

import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List
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
# Minimal AgentBenchmarkResult for save_results agent tests
# ---------------------------------------------------------------------------

@dataclass
class _FakeAgentResult:
    """Minimal stand-in for AgentBenchmarkResult used in save_results tests."""
    model: str = "m"
    fixture: str = "f"
    timestamp: str = "2024-01-01T00:00:00"
    run_number: int = 1
    compiles: bool = True
    compilation_errors: List[str] = field(default_factory=list)
    compilation_warnings: List[str] = field(default_factory=list)
    pattern_score: float = 8.0
    ast_missing: List[str] = field(default_factory=list)
    ast_checks: dict = field(default_factory=dict)
    naming_score: float = 8.0
    naming_violations: List[str] = field(default_factory=list)
    final_score: float = 7.0
    scoring_weights: dict = field(default_factory=dict)
    tokens_per_sec: float = 30.0
    duration_sec: float = 10.0
    output_code: str = ""
    errors: List[str] = field(default_factory=list)
    steps: int = 2
    max_steps: int = 10
    iterations: int = 2
    succeeded: bool = True
    tool_call_log: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"step": 1, "tool": "write_file", "compile_passed": False, "duration_sec": 3.1, "context_chars": 800, "result_summary": "errors"},
        {"step": 2, "tool": "write_file", "compile_passed": True, "duration_sec": 2.8, "context_chars": 900, "result_summary": "ok"},
    ])


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
# save_results — agent mode (folder output)
# ---------------------------------------------------------------------------

class TestSaveAgentResults:
    def _make_agent_results(self, n=2):
        return [_FakeAgentResult(run_number=i + 1) for i in range(n)]

    def test_agent_save_creates_folder_not_file(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results()
        out = save_results(results, "mymodel", "nuxt-form-agent-guided", requested_runs=2)
        assert out.is_dir()

    def test_agent_folder_name_contains_model_fixture_runs(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results(3)
        out = save_results(results, "mymodel:7b", "nuxt-form-agent-guided", requested_runs=3)
        assert "mymodel" in out.name
        assert "nuxt-form-agent-guided" in out.name
        assert "3runs" in out.name

    def test_agent_folder_name_no_colon(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results()
        out = save_results(results, "model:7b", "fixture", requested_runs=2)
        assert ":" not in out.name

    def test_agent_save_creates_summary_json(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results()
        out = save_results(results, "m", "f", requested_runs=2)
        assert (out / "summary.json").exists()

    def test_agent_save_creates_steps_jsonl(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results()
        out = save_results(results, "m", "f", requested_runs=2)
        assert (out / "steps.jsonl").exists()

    def test_summary_json_has_n_runs_and_runs_array(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results(2)
        out = save_results(results, "m", "f", requested_runs=2)
        data = json.loads((out / "summary.json").read_text())
        assert data["n_runs"] == 2
        assert isinstance(data["runs"], list)
        assert len(data["runs"]) == 2

    def test_steps_jsonl_has_one_line_per_tool_call_per_run(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        # Each _FakeAgentResult has 2 tool_call_log entries, 2 runs = 4 lines
        results = self._make_agent_results(2)
        out = save_results(results, "m", "f", requested_runs=2)
        lines = [l for l in (out / "steps.jsonl").read_text().splitlines() if l.strip()]
        assert len(lines) == 4

    def test_steps_jsonl_entries_have_run_field(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results(1)
        out = save_results(results, "m", "f", requested_runs=1)
        lines = (out / "steps.jsonl").read_text().splitlines()
        entry = json.loads(lines[0])
        assert "run" in entry

    def test_steps_jsonl_entries_have_step_tool_compile_passed(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results(1)
        out = save_results(results, "m", "f", requested_runs=1)
        lines = (out / "steps.jsonl").read_text().splitlines()
        entry = json.loads(lines[0])
        assert "step" in entry
        assert "tool" in entry
        assert "compile_passed" in entry

    def test_steps_jsonl_no_args_content(self, tmp_path, monkeypatch):
        """steps.jsonl must not include args (could contain full file content)."""
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        results = self._make_agent_results(1)
        out = save_results(results, "m", "f", requested_runs=1)
        lines = (out / "steps.jsonl").read_text().splitlines()
        for line in lines:
            assert "args" not in json.loads(line)

    def test_existing_agent_output_dir_used_if_provided(self, tmp_path, monkeypatch):
        """If agent_output_dir is given, use it (for prompt_log co-location)."""
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        preset_dir = tmp_path / "preset_dir"
        results = self._make_agent_results(1)
        out = save_results(results, "m", "f", requested_runs=1, agent_output_dir=preset_dir)
        assert out == preset_dir
        assert (preset_dir / "summary.json").exists()

    def test_single_shot_still_returns_json_file(self, tmp_path, monkeypatch):
        import run_test
        monkeypatch.setattr(run_test, "OUTPUT_DIR", tmp_path)
        result = make_result()
        path = save_results([result], "m", "single-shot")
        assert path.is_file()
        assert path.suffix == ".json"


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
