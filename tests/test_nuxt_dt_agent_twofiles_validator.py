"""Tests for src/agent/nuxt_dt_agent_twofiles/validator.py.

DataTable scoring rules (0-10):
  +1  script_lang, +1 datatable_component, +2 render_function,
  +1  currency_formatter, +1 date_formatter, +1 status_badge,
  +2  action_handlers, +1 column_ids (>=5 of 6)

In the two-files variant, columns live in a separate file — validate_ast_structure
receives combined code (vue + columns.ts) so all checks still pass.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.agent.nuxt_dt_agent_twofiles.validator import (
    ASTResult,
    CompilationResult,
    NamingResult,
    validate_ast_structure,
    validate_compilation,
    validate_naming,
)

COMPLETE_COMPONENT = """
<script setup lang="ts">
import { DataTable, Button } from "elements";
import type { Column } from "elements";
import { h } from "vue";
import { orders } from "./data";
import type { Order, OrderStatus } from "./types";

const statusLabels: Record<OrderStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const statusClasses: Record<OrderStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  shipped: "bg-purple-100 text-purple-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

const props = defineProps<{
  onView: (order: Order) => void;
  onCancel: (order: Order) => void;
}>();

const columns: Column<Order>[] = [
  { id: "id", label: "Order", cell: ({ row }) => h("span", { class: "font-mono" }, `#ORD-${row.getValue("id")}`) },
  { id: "customer", label: "Customer", isSortable: true },
  { id: "status", label: "Status", cell: ({ row }) => {
    const status = row.getValue("status") as OrderStatus;
    return h("span", { class: statusClasses[status] }, statusLabels[status]);
  }},
  { id: "items", label: "Items", isSortable: true },
  { id: "total", label: "Total", isSortable: true, cell: ({ row }) => {
    const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number.parseFloat(row.getValue("total") as string));
    return h("div", { class: "text-right font-medium" }, formatted);
  }},
  { id: "date", label: "Date", isSortable: true, cell: ({ row }) => {
    const formatted = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(row.getValue("date") as string));
    return h("span", {}, formatted);
  }},
  { id: "actions", cell: ({ row }) => [
    h(Button, { variant: "ghost", size: "sm", onClick: () => props.onView(row.original) }, () => "View"),
    h(Button, { variant: "destructive", size: "sm", onClick: () => props.onCancel(row.original) }, () => "Cancel"),
  ]},
];
</script>

<template>
  <DataTable :columns="columns" :data="orders" :config="{ filter: true, filterModel: 'customer' }" />
</template>
"""

COLUMNS_CODE = """
import type { Column } from "elements";
import { Button } from "elements";
import { h } from "vue";
import type { Order, OrderStatus } from "./types";

const statusLabels: Record<OrderStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const statusClasses: Record<OrderStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  shipped: "bg-purple-100 text-purple-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

export interface OrderColumnHandlers {
  onView: (order: Order) => void;
  onCancel: (order: Order) => void;
}

export const createColumns = (handlers: OrderColumnHandlers): Column<Order>[] => [
  { id: "id", label: "Order", cell: ({ row }) => h("span", {}, `#ORD-${row.getValue("id")}`) },
  { id: "customer", label: "Customer", isSortable: true },
  { id: "status", label: "Status", cell: ({ row }) => {
    const status = row.getValue("status") as OrderStatus;
    return h("span", { class: statusClasses[status] }, statusLabels[status]);
  }},
  { id: "items", label: "Items", isSortable: true },
  { id: "total", label: "Total", isSortable: true, cell: ({ row }) => {
    return h("div", { class: "text-right" }, new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number.parseFloat(row.getValue("total") as string)));
  }},
  { id: "date", label: "Date", isSortable: true, cell: ({ row }) => {
    return h("span", {}, new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(row.getValue("date") as string)));
  }},
  { id: "actions", cell: ({ row }) => [
    h(Button, { variant: "ghost", onClick: () => handlers.onView(row.original) }, () => "View"),
    h(Button, { variant: "destructive", onClick: () => handlers.onCancel(row.original) }, () => "Cancel"),
  ]},
];
"""

COMBINED_CODE = COMPLETE_COMPONENT + "\n\n// --- columns.ts ---\n" + COLUMNS_CODE

SPEC = {
    "script_lang": "ts",
    "datatable_component": "<DataTable",
    "render_function": "h(",
    "currency_formatter": "Intl.NumberFormat",
    "date_formatter": "Intl.DateTimeFormat",
    "status_badge": "status",
    "action_handlers": ["onView", "onCancel"],
    "column_ids": ["id", "customer", "status", "total", "date", "actions"],
}


class TestValidateAstStructure:

    def test_complete_code_scores_ten(self):
        result = validate_ast_structure(COMPLETE_COMPONENT, SPEC)
        assert result.score == pytest.approx(10.0)
        assert result.missing == []

    def test_returns_ast_result_instance(self):
        assert isinstance(validate_ast_structure(COMPLETE_COMPONENT, SPEC), ASTResult)

    def test_empty_string_scores_zero(self):
        assert validate_ast_structure("", SPEC).score == pytest.approx(0.0)

    def test_missing_script_lang_ts_reduces_score(self):
        code = COMPLETE_COMPONENT.replace('lang="ts"', 'lang="js"')
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "script_lang" in result.missing

    def test_missing_datatable_component_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("<DataTable ", "<DataTableWrapper ")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "datatable_component" in result.missing

    def test_missing_render_function_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("h(", "render(")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(8.0)
        assert "render_function" in result.missing

    def test_missing_currency_formatter_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("Intl.NumberFormat", "CurrencyFormat")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "currency_formatter" in result.missing

    def test_missing_date_formatter_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("Intl.DateTimeFormat", "DateFormat")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "date_formatter" in result.missing

    def test_missing_status_badge_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("statusClasses", "colorMap").replace("statusLabels", "labelMap")
        code = code.replace('status === "', 'value === "')
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "status_badge" in result.missing

    def test_only_on_view_handler_partial_score(self):
        code = COMPLETE_COMPONENT.replace("onCancel", "REMOVED_HANDLER")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "action_handlers" in result.missing

    def test_no_action_handlers_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("onView", "REMOVED1").replace("onCancel", "REMOVED2")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(8.0)
        assert "action_handlers" in result.missing

    def test_four_of_six_column_ids_fails(self):
        code = COMPLETE_COMPONENT.replace('{ id: "date"', '{ id: "removed_date"')
        code = code.replace('{ id: "actions"', '{ id: "removed_actions"')
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "column_ids" in result.missing

    def test_five_of_six_column_ids_passes(self):
        code = COMPLETE_COMPONENT.replace('{ id: "actions"', '{ id: "removed_actions"')
        result = validate_ast_structure(code, SPEC)
        assert "column_ids" not in result.missing

    def test_checks_dict_populated(self):
        result = validate_ast_structure(COMPLETE_COMPONENT, SPEC)
        assert result.checks.get("script_lang") is True
        assert result.checks.get("datatable_component") is True
        assert result.checks.get("render_function") is True

    def test_combined_vue_and_columns_code_scores_ten(self):
        """Validator must work on combined code from both files."""
        columns_code = "import { h } from 'vue';\nconst statusClasses = {};\nexport const createColumns = (handlers) => [\n  { id: 'id' }, { id: 'customer' }, { id: 'status' }, { id: 'total' }, { id: 'date' }, { id: 'actions' },\n  ...[{ cell: () => h('div', {}, new Intl.NumberFormat('en-US').format(1)) }],\n  ...[{ cell: () => h('span', {}, new Intl.DateTimeFormat('en-US').format(new Date())) }],\n];\n// onView onCancel"
        combined = COMPLETE_COMPONENT + "\n\n// --- columns.ts ---\n" + columns_code
        result = validate_ast_structure(combined, SPEC)
        assert result.score == pytest.approx(10.0)


class TestValidateCompilation:

    def test_success_on_zero_returncode(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert validate_compilation(tmp_path, "check-types", tmp_path).success is True

    def test_failure_on_nonzero_returncode(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stdout="", stderr="error TS2307: missing")
            assert validate_compilation(tmp_path, "check-types", tmp_path).success is False

    def test_raises_on_missing_project(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_compilation(tmp_path / "nx", "check-types", tmp_path / "nx")

    def test_returns_compilation_result(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert isinstance(validate_compilation(tmp_path, "check-types", tmp_path), CompilationResult)


class TestValidateNaming:

    def test_camelcase_scores_one(self):
        assert validate_naming("const statusClasses = {}", {"variables": "camelCase"}).score == pytest.approx(1.0)

    def test_uppercase_scores_zero(self):
        assert validate_naming("const MyVar = {}", {"variables": "camelCase"}).score == pytest.approx(0.0)

    def test_empty_conventions_no_violations(self):
        assert validate_naming("const BadName = {}", {}).score == pytest.approx(1.0)

    def test_returns_naming_result(self):
        assert isinstance(validate_naming("", {"variables": "camelCase"}), NamingResult)
