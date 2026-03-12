/**
 * EXAMPLE: Action column using createColumns(handlers) factory pattern.
 *
 * Patterns shown:
 * - Define a handlers interface with typed callback functions
 * - createColumns(handlers): Column<T>[] is a factory — closures capture handlers
 * - id: "actions" is a special convention: the DataTable wrapper auto-adds flex layout
 * - h(Button, { onClick: () => handlers.fn(row.original) }, () => "Label")
 * - row.original gives typed access to the full row data object
 * - Import Button from "elements" for action buttons
 */

import type { Column } from "elements";
import { Button } from "elements";
import { h } from "vue";

interface Employee {
  id: string;
  name: string;
  department: string;
}

// Handlers interface — passed to createColumns factory
export interface EmployeeColumnHandlers {
  onEdit: (employee: Employee) => void;
  onDelete: (employee: Employee) => void;
}

// Factory function: columns are created with handlers captured in closure
export const createColumns = (
  handlers: EmployeeColumnHandlers,
): Column<Employee>[] => [
  {
    id: "name",
    label: "Name",
    isSortable: true,
  },
  {
    id: "department",
    label: "Department",
    isSortable: true,
  },
  {
    // id: "actions" — special convention: DataTable adds flex layout automatically
    id: "actions",
    cell: ({ row }) => [
      // h(Component, props, slot) — slot must be a function returning content
      h(
        Button,
        {
          variant: "ghost",
          size: "sm",
          onClick: () => handlers.onEdit(row.original),
        },
        () => "Edit",
      ),
      h(
        Button,
        {
          variant: "destructive",
          size: "sm",
          onClick: () => handlers.onDelete(row.original),
        },
        () => "Delete",
      ),
    ],
  },
];
