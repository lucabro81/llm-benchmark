"""Tests for src/creation/nuxt_dt_oneshot/test_runner.py.

Key differences from nuxt_form_oneshot runner:
- target file: apps/web/src/orders/OrdersDataTable.vue
- stub: "<!-- TODO: implement OrdersDataTable component -->\n"
- Compilation uses compilation_cwd + compilation_command (npm run check-types from apps/web)
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.creation.nuxt_dt_oneshot.test_runner import BenchmarkResult, CreationTest

STUB_VUE = "<!-- TODO: implement OrdersDataTable component -->\n"

COMPLETE_VUE = """<script setup lang="ts">
import { DataTable, Button } from "elements";
import type { Column } from "elements";
import { h } from "vue";
import { orders } from "./data";
import type { Order, OrderStatus } from "./types";

const statusClasses: Record<OrderStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  delivered: "bg-green-100 text-green-800",
};

const props = defineProps<{
  onView: (order: Order) => void;
  onCancel: (order: Order) => void;
}>();

const columns: Column<Order>[] = [
  { id: "id", label: "Order", cell: ({ row }) => h("span", {}, row.getValue("id")) },
  { id: "customer", label: "Customer", isSortable: true },
  { id: "status", label: "Status", cell: ({ row }) => h("span", { class: statusClasses[row.getValue("status") as OrderStatus] }, row.getValue("status")) },
  { id: "total", label: "Total", cell: ({ row }) => h("div", {}, new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number.parseFloat(row.getValue("total") as string))) },
  { id: "date", label: "Date", cell: ({ row }) => h("span", {}, new Intl.DateTimeFormat("en-US").format(new Date(row.getValue("date") as string))) },
  { id: "actions", cell: ({ row }) => [
    h(Button, { onClick: () => props.onView(row.original) }, () => "View"),
    h(Button, { onClick: () => props.onCancel(row.original) }, () => "Cancel"),
  ]},
];
</script>

<template>
  <DataTable :columns="columns" :data="orders" />
</template>
"""

DEFAULT_SPEC = {
    "target_project_path": "../shared_target_project",
    "target_file": "apps/web/src/orders/OrdersDataTable.vue",
    "compilation_cwd": "apps/web",
    "compilation_command": "check-types",
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
    """Create fixture dir + separate shared target_project."""
    shared_tp = tmp_path / "shared_target_project"
    orders_dir = shared_tp / "apps" / "web" / "src" / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    (orders_dir / "OrdersDataTable.vue").write_text(STUB_VUE)

    fixture_path = tmp_path / "nuxt-dt-oneshot"
    fixture_path.mkdir(exist_ok=True)
    (fixture_path / "prompt.md").write_text("Implement an orders data table.")
    target_spec = spec if spec is not None else DEFAULT_SPEC
    (fixture_path / "validation_spec.json").write_text(json.dumps(target_spec))

    return fixture_path


def _make_chat_result(response="```vue\n" + COMPLETE_VUE + "\n```"):
    return SimpleNamespace(
        response_text=response,
        tokens_per_sec=30.0,
        duration_sec=5.0,
    )


def _make_compilation_result(success=True, errors=None, warnings=None):
    return SimpleNamespace(success=success, errors=errors or [], warnings=warnings or [], duration_sec=1.0)


def _make_ast_result(score=10.0, missing=None, checks=None):
    return SimpleNamespace(score=score, missing=missing or [], checks=checks or {"script_lang": True})


def _make_naming_result(score=1.0, violations=None):
    return SimpleNamespace(score=score, violations=violations or [], follows_conventions=score == 1.0)


# ---------------------------------------------------------------------------
# CreationTest init
# ---------------------------------------------------------------------------

class TestCreationTestInit:

    def test_loads_prompt_and_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = CreationTest(model="test-model", fixture_path=fixture_path)
        assert "data table" in test.prompt_template.lower()
        assert test.validation_spec["target_file"].endswith("OrdersDataTable.vue")

    def test_resolves_target_project_from_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = CreationTest(model="test-model", fixture_path=fixture_path)
        assert test.target_project == (tmp_path / "shared_target_project").resolve()

    def test_raises_on_missing_prompt(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        with pytest.raises(FileNotFoundError, match="prompt.md"):
            CreationTest(model="m", fixture_path=fixture_path)

    def test_raises_when_target_project_not_found(self, tmp_path):
        fixture_path = tmp_path / "nuxt-dt-oneshot"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        spec = dict(DEFAULT_SPEC)
        spec["target_project_path"] = "../nonexistent"
        (fixture_path / "validation_spec.json").write_text(json.dumps(spec))
        with pytest.raises(FileNotFoundError):
            CreationTest(model="m", fixture_path=fixture_path)

    def test_has_prompt_template_attribute(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = CreationTest(model="test-model", fixture_path=fixture_path)
        assert hasattr(test, "prompt_template")
        assert isinstance(test.prompt_template, str)
        assert len(test.prompt_template) > 0


# ---------------------------------------------------------------------------
# CreationTest.run()
# ---------------------------------------------------------------------------

class TestCreationTestRun:

    @patch("src.creation.nuxt_dt_oneshot.test_runner.validator")
    @patch("src.creation.nuxt_dt_oneshot.test_runner.ollama_client")
    def test_returns_benchmark_result(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = CreationTest(model="m", fixture_path=fixture_path).run(run_number=1)
        assert isinstance(result, BenchmarkResult)

    @patch("src.creation.nuxt_dt_oneshot.test_runner.validator")
    @patch("src.creation.nuxt_dt_oneshot.test_runner.ollama_client")
    def test_perfect_score(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=10.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=1.0)

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert result.final_score == pytest.approx(10.0)

    @patch("src.creation.nuxt_dt_oneshot.test_runner.validator")
    @patch("src.creation.nuxt_dt_oneshot.test_runner.ollama_client")
    def test_stub_restored_after_run(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "OrdersDataTable.vue"

        def side_effect(*args, **kwargs):
            target_vue.write_text(COMPLETE_VUE)
            return _make_chat_result(response=COMPLETE_VUE)

        mock_ollama.chat.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        CreationTest(model="m", fixture_path=fixture_path).run()
        assert target_vue.read_text() == STUB_VUE

    @patch("src.creation.nuxt_dt_oneshot.test_runner.validator")
    @patch("src.creation.nuxt_dt_oneshot.test_runner.ollama_client")
    def test_stub_restored_on_exception(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "orders" / "OrdersDataTable.vue"
        mock_ollama.chat.side_effect = RuntimeError("crash")

        test = CreationTest(model="m", fixture_path=fixture_path)
        with pytest.raises(RuntimeError):
            test.run()

        assert target_vue.read_text() == STUB_VUE


# ---------------------------------------------------------------------------
# extract_vue_code
# ---------------------------------------------------------------------------

class TestExtractVueCode:

    @patch("src.creation.nuxt_dt_oneshot.test_runner.validator")
    @patch("src.creation.nuxt_dt_oneshot.test_runner.ollama_client")
    def test_extracts_vue_from_fence(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        fenced = "```vue\n" + COMPLETE_VUE + "\n```"
        mock_ollama.chat.return_value = _make_chat_result(response=fenced)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert "<script" in result.output_code
        assert "```" not in result.output_code

    @patch("src.creation.nuxt_dt_oneshot.test_runner.validator")
    @patch("src.creation.nuxt_dt_oneshot.test_runner.ollama_client")
    def test_extracts_from_plain_code_fence(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        fenced = "```\n" + COMPLETE_VUE + "\n```"
        mock_ollama.chat.return_value = _make_chat_result(response=fenced)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert "<script" in result.output_code

    @patch("src.creation.nuxt_dt_oneshot.test_runner.validator")
    @patch("src.creation.nuxt_dt_oneshot.test_runner.ollama_client")
    def test_returns_raw_if_no_fence(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        raw = COMPLETE_VUE
        mock_ollama.chat.return_value = _make_chat_result(response=raw)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert "<script" in result.output_code
