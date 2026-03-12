"""Tests for src/agent/nuxt_dt_agent_full/test_runner.py.

Key differences from nuxt-dt-agent-rag runner:
- Three stub files restored (OrdersDataTable.vue + columns.ts + types.ts)
- Custom tools: read_file + list_files + write_file + run_compilation + query_rag
- validate_ast_structure receives combined code from all three files
- max_steps: 30
- allowed_write_paths includes types.ts, columns.ts, and OrdersDataTable.vue
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.nuxt_dt_agent_full.test_runner import AgentBenchmarkResult, AgentTest

STUB_VUE = "<!-- TODO: implement OrdersDataTable component -->\n"
STUB_COLUMNS = "// TODO: implement column definitions for OrdersDataTable\n"
STUB_TYPES = "// TODO: implement Order types\n"

DEFAULT_SPEC = {
    "target_project_path": "../shared_target_project",
    "rag_docs_path": "../rag_docs",
    "target_file": "apps/web/src/orders/OrdersDataTable.vue",
    "allowed_write_paths": [
        "apps/web/src/orders/types.ts",
        "apps/web/src/orders/columns.ts",
        "apps/web/src/orders/OrdersDataTable.vue",
    ],
    "compilation_cwd": "apps/web",
    "compilation_command": "check-types",
    "max_steps": 30,
    "required_patterns": {
        "script_lang": "ts",
        "datatable_component": "<DataTable",
        "render_function": "h(",
        "currency_formatter": "Intl.NumberFormat",
        "date_formatter": "Intl.DateTimeFormat",
        "status_badge": "status",
        "action_handlers": ["onView", "onCancel"],
        "column_ids": ["id", "customer", "status", "total", "date", "actions"],
    },
    "naming_conventions": {"variables": "camelCase"},
    "scoring": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
}


def _make_fixture(tmp_path: Path, spec=None) -> Path:
    shared_tp = tmp_path / "shared_target_project"
    orders_dir = shared_tp / "apps" / "web" / "src" / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    (orders_dir / "OrdersDataTable.vue").write_text(STUB_VUE)
    (orders_dir / "columns.ts").write_text(STUB_COLUMNS)
    (orders_dir / "types.ts").write_text(STUB_TYPES)

    rag_docs = tmp_path / "rag_docs"
    rag_docs.mkdir(exist_ok=True)
    (rag_docs / "01_example.ts").write_text("// DataTable example\nconst columns = [];")

    fixture_path = tmp_path / "nuxt-dt-agent-full"
    fixture_path.mkdir(exist_ok=True)
    (fixture_path / "prompt.md").write_text("Implement an orders data table using query_rag.")
    target_spec = spec if spec is not None else DEFAULT_SPEC
    (fixture_path / "validation_spec.json").write_text(json.dumps(target_spec))
    return fixture_path


def _make_agent_result(**kwargs):
    defaults = dict(
        succeeded=True, steps=6, final_output="Done",
        tool_call_log=[
            {"step": 1, "tool": "query_rag", "args": {"query": "datatable"}, "result_summary": "..."},
            {"step": 2, "tool": "read_file", "args": {}, "result_summary": "read"},
            {"step": 3, "tool": "write_file", "args": {}, "result_summary": "types written"},
            {"step": 4, "tool": "write_file", "args": {}, "result_summary": "columns written"},
            {"step": 5, "tool": "write_file", "args": {}, "result_summary": "component written"},
        ],
        duration_sec=15.0, tokens_per_sec=18.0, errors=[],
        total_input_tokens=600, total_output_tokens=250,
        first_compile_success_step=3, compile_error_recovery_count=0,
        rag_queries_count=1, read_file_count=2, list_files_count=1,
        run_crashed=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_compilation_result(success=True, errors=None, warnings=None):
    return SimpleNamespace(success=success, errors=errors or [], warnings=warnings or [])


def _make_ast_result(score=10.0, missing=None, checks=None):
    return SimpleNamespace(score=score, missing=missing or [], checks=checks or {"script_lang": True})


def _make_naming_result(score=1.0, violations=None):
    return SimpleNamespace(score=score, violations=violations or [])


# ---------------------------------------------------------------------------
# AgentBenchmarkResult
# ---------------------------------------------------------------------------

class TestAgentBenchmarkResult:

    def test_all_fields_present(self):
        r = AgentBenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=10.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=10.0,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[], steps=6, max_steps=30, iterations=3,
            succeeded=True, tool_call_log=[], aborted=False,
        )
        assert r.max_steps == 30
        assert r.aborted is False


# ---------------------------------------------------------------------------
# AgentTest init
# ---------------------------------------------------------------------------

class TestAgentTestInit:

    def test_loads_prompt_and_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert "query_rag" in test.prompt.lower()
        assert test.validation_spec["target_file"].endswith("OrdersDataTable.vue")

    def test_resolves_target_project_from_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert test.target_project == (tmp_path / "shared_target_project").resolve()

    def test_reads_max_steps(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        assert AgentTest(model="m", fixture_path=fixture_path).max_steps == 30

    def test_raises_on_missing_prompt(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        with pytest.raises(FileNotFoundError, match="prompt.md"):
            AgentTest(model="m", fixture_path=fixture_path)

    def test_raises_when_target_project_not_found(self, tmp_path):
        fixture_path = tmp_path / "nuxt-dt-agent-full"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        spec = dict(DEFAULT_SPEC)
        spec["target_project_path"] = "../nonexistent"
        (fixture_path / "validation_spec.json").write_text(json.dumps(spec))
        with pytest.raises(FileNotFoundError):
            AgentTest(model="m", fixture_path=fixture_path)

    def test_raises_when_rag_docs_not_found(self, tmp_path):
        fixture_path = tmp_path / "nuxt-dt-agent-full"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        spec = dict(DEFAULT_SPEC)
        spec["rag_docs_path"] = "../nonexistent_rag"
        (fixture_path / "validation_spec.json").write_text(json.dumps(spec))
        # Create shared_target_project
        shared_tp = tmp_path / "shared_target_project"
        orders_dir = shared_tp / "apps" / "web" / "src" / "orders"
        orders_dir.mkdir(parents=True, exist_ok=True)
        (orders_dir / "OrdersDataTable.vue").write_text(STUB_VUE)
        (orders_dir / "columns.ts").write_text(STUB_COLUMNS)
        (orders_dir / "types.ts").write_text(STUB_TYPES)
        with pytest.raises(FileNotFoundError):
            AgentTest(model="m", fixture_path=fixture_path)


# ---------------------------------------------------------------------------
# AgentTest.run() — tool composition
# ---------------------------------------------------------------------------

class TestAgentTestTools:

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_has_query_rag_in_tools(self, mock_run_agent, mock_validator, tmp_path):
        """Full agent must have query_rag tool."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "query_rag" in tool_names

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_has_read_file_in_tools(self, mock_run_agent, mock_validator, tmp_path):
        """Full agent must have read_file tool."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "read_file" in tool_names

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_has_list_files_in_tools(self, mock_run_agent, mock_validator, tmp_path):
        """Full agent must have list_files tool."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "list_files" in tool_names

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_has_write_file_and_run_compilation(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "write_file" in tool_names
        assert "run_compilation" in tool_names


# ---------------------------------------------------------------------------
# AgentTest.run() — scoring + restoration
# ---------------------------------------------------------------------------

class TestAgentTestRun:

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_returns_agent_benchmark_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run()
        assert isinstance(result, AgentBenchmarkResult)

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_perfect_score(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=10.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=1.0)

        result = AgentTest(model="m", fixture_path=fixture_path).run()
        assert result.final_score == pytest.approx(10.0)

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_all_three_stubs_restored_after_run(self, mock_run_agent, mock_validator, tmp_path):
        """All three stubs (OrdersDataTable.vue, columns.ts, types.ts) must be restored."""
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "OrdersDataTable.vue"
        target_columns = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "columns.ts"
        target_types = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "types.ts"

        def side_effect(*args, **kwargs):
            target_vue.write_text("<script setup lang='ts'>changed</script>")
            target_columns.write_text("export const createColumns = () => [];")
            target_types.write_text("export type OrderStatus = 'pending';")
            return _make_agent_result()

        mock_run_agent.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()
        assert target_vue.read_text() == STUB_VUE
        assert target_columns.read_text() == STUB_COLUMNS
        assert target_types.read_text() == STUB_TYPES

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_stub_restored_on_exception(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "OrdersDataTable.vue"
        mock_run_agent.side_effect = RuntimeError("crash")

        test = AgentTest(model="m", fixture_path=fixture_path)
        with pytest.raises(RuntimeError):
            test.run()

        assert target_vue.read_text() == STUB_VUE

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_combined_output_includes_all_three_files_separator(self, mock_run_agent, mock_validator, tmp_path):
        """output_code must concatenate vue + columns + types with separators."""
        fixture_path = _make_fixture(tmp_path)
        columns_path = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "columns.ts"
        types_path = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "types.ts"

        def side_effect(*args, **kwargs):
            columns_path.write_text("export const createColumns = () => [];")
            types_path.write_text("export type OrderStatus = 'pending' | 'delivered';")
            return _make_agent_result()

        mock_run_agent.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run()
        assert "// --- columns.ts ---" in result.output_code or "// --- types.ts ---" in result.output_code


# ---------------------------------------------------------------------------
# AgentTest.run() — aborted run handling
# ---------------------------------------------------------------------------

class TestAbortedRun:

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_aborted_true_when_run_crashed(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0, errors=["Ollama error"])

        result = AgentTest(model="m", fixture_path=fixture_path).run()

        assert result.aborted is True

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_aborted_run_scores_are_zero(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0)

        result = AgentTest(model="m", fixture_path=fixture_path).run()

        assert result.final_score == 0.0
        assert result.pattern_score == 0.0
        assert result.naming_score == 0.0
        assert result.compiles is False

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_aborted_run_skips_validation(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0)

        AgentTest(model="m", fixture_path=fixture_path).run()

        mock_validator.validate_compilation.assert_not_called()
        mock_validator.validate_ast_structure.assert_not_called()
        mock_validator.validate_naming.assert_not_called()

    @patch("src.agent.nuxt_dt_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_dt_agent_full.test_runner.run_agent")
    def test_non_crashed_run_not_aborted(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=False)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run()

        assert result.aborted is False


# ---------------------------------------------------------------------------
# write_file decoupling — tool must only write, not compile
# ---------------------------------------------------------------------------

class TestWriteFileDecoupled:

    def test_write_file_returns_file_written_only(self, tmp_path):
        """After decoupling, write_file must return 'File written.' with no compilation output."""
        from src.agent.nuxt_dt_agent_full.test_runner import _make_tools

        allowed_path = "apps/web/src/orders/OrdersDataTable.vue"
        orders_dir = tmp_path / "apps" / "web" / "src" / "orders"
        orders_dir.mkdir(parents=True, exist_ok=True)
        (orders_dir / "OrdersDataTable.vue").write_text(STUB_VUE)

        mock_rag_tool = MagicMock()
        mock_rag_tool.name = "query_rag"
        tools = _make_tools(
            target_project=tmp_path,
            allowed_paths=[allowed_path],
            compilation_cwd=tmp_path,
            compilation_command="check-types",
            rag_tool=mock_rag_tool,
        )
        write_tool = next(t for t in tools if t.name == "write_file")
        result = write_tool(path=allowed_path, content="<script setup lang='ts'>new</script>")

        assert result == "File written."
        assert "Compilation" not in result
