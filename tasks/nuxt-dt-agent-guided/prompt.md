You are implementing a Vue 3 data table component in a Turborepo monorepo.

## Task

Implement `OrdersDataTable.vue` at:
`apps/web/src/orders/OrdersDataTable.vue`

### Columns required

| Column     | id        | Details                                                          |
|------------|-----------|------------------------------------------------------------------|
| Order      | `id`      | Display as `#ORD-{value}` in a monospace span                    |
| Customer   | `customer`| Plain text, sortable                                             |
| Status     | `status`  | Badge with per-status CSS class and label (use Record lookup maps)|
| Items      | `items`   | Plain number, sortable                                           |
| Total      | `total`   | Currency, formatted with `Intl.NumberFormat` (USD), sortable    |
| Date       | `date`    | Formatted with `Intl.DateTimeFormat` (medium style), sortable   |
| Actions    | `actions` | Two buttons: View (ghost) and Cancel (destructive)              |

### Props

```ts
defineProps<{
  onView: (order: Order) => void;
  onCancel: (order: Order) => void;
}>()
```

## How to use your tools

Use `write_file` to write the component, then `run_compilation` to check for TypeScript errors:
- Path: `apps/web/src/orders/OrdersDataTable.vue`
- `write_file` only writes the file and returns `"File written."` — it does NOT compile
- After writing, always call `run_compilation` to get TypeScript feedback
- Fix any errors reported and repeat until compilation succeeds

Write a **single Vue SFC** file:
- Use `<script setup lang="ts">`
- Import `Order`, `OrderStatus` from `./types` and `orders` from `./data` (these files exist)
- Define columns inline in the script block

---

## Component API Reference

Use ONLY the components from the `elements` package shown below.

### 01_basic_datatable.vue

```vue
<!--
  EXAMPLE: Basic DataTable with static text columns and filter config.

  Pattern:
  - Import DataTable and Column type from "elements"
  - Define columns array: Column<T>[] with id, label, isSortable
  - Pass :columns, :data, :config to <DataTable>
  - config: { filter: true, filterModel: "fieldName" } enables a search box
-->
<script setup lang="ts">
import { DataTable } from "elements";
import type { Column } from "elements";

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
}

const users: User[] = [
  { id: "1", name: "Alice", email: "alice@example.com", role: "admin" },
  { id: "2", name: "Bob", email: "bob@example.com", role: "user" },
];

const columns: Column<User>[] = [
  { id: "name", label: "Name", isSortable: true },
  { id: "email", label: "Email", isSortable: true },
  { id: "role", label: "Role", isSortable: false },
];
</script>

<template>
  <DataTable
    :columns="columns"
    :data="users"
    :config="{ filter: true, filterModel: 'name' }"
  />
</template>
```

### 02_formatter_cells.ts

```ts
/**
 * EXAMPLE: Custom cell renderers using Vue h() and Intl formatters.
 *
 * - Import h from "vue" for render functions
 * - row.getValue("fieldName") returns the raw cell value (cast as needed)
 * - Intl.NumberFormat for currency formatting
 * - Intl.DateTimeFormat for date formatting
 */
import type { Column } from "elements";
import { h } from "vue";

interface Product {
  id: string;
  name: string;
  price: number;
  releaseDate: string;
}

export const columns: Column<Product>[] = [
  { id: "name", label: "Product", isSortable: true },

  // Currency formatter
  {
    id: "price",
    label: "Price",
    isSortable: true,
    cell: ({ row }) => {
      const amount = Number.parseFloat(row.getValue("price") as string);
      const formatted = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(amount);
      return h("div", { class: "text-right font-medium" }, formatted);
    },
  },

  // Date formatter
  {
    id: "releaseDate",
    label: "Release Date",
    isSortable: true,
    cell: ({ row }) => {
      const rawDate = row.getValue("releaseDate") as string;
      const formatted = new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium",
      }).format(new Date(rawDate));
      return h("span", { class: "text-sm text-gray-600" }, formatted);
    },
  },
];
```

### 03_status_badge.ts

```ts
/**
 * EXAMPLE: Status badge column using Record<Status, string> lookup maps.
 *
 * - Define a Status type as union of string literals
 * - Use Record<Status, string> for label and CSS class maps
 * - row.getValue("status") as Status — cast to typed status
 * - h("span", { class: dynamicClass }, labelText) renders the badge
 */
import type { Column } from "elements";
import { h } from "vue";

type ItemStatus = "active" | "inactive" | "pending" | "suspended";

interface Item {
  id: string;
  name: string;
  status: ItemStatus;
}

const statusLabels: Record<ItemStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  pending: "Pending",
  suspended: "Suspended",
};

const statusClasses: Record<ItemStatus, string> = {
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-800",
  pending: "bg-yellow-100 text-yellow-800",
  suspended: "bg-red-100 text-red-800",
};

export const columns: Column<Item>[] = [
  { id: "name", label: "Name", isSortable: true },
  {
    id: "status",
    label: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as ItemStatus;
      return h(
        "span",
        { class: `inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${statusClasses[status]}` },
        statusLabels[status],
      );
    },
  },
];
```

### 04_action_columns.ts

```ts
/**
 * EXAMPLE: Action column with typed handler callbacks.
 *
 * - h(Button, { onClick: () => handlers.fn(row.original) }, () => "Label")
 * - row.original gives typed access to the full row data object
 * - Import Button from "elements"
 * - id: "actions" is a special convention: DataTable auto-adds flex layout
 */
import type { Column } from "elements";
import { Button } from "elements";
import { h } from "vue";

interface Employee {
  id: string;
  name: string;
  department: string;
}

export interface EmployeeColumnHandlers {
  onEdit: (employee: Employee) => void;
  onDelete: (employee: Employee) => void;
}

export const createColumns = (handlers: EmployeeColumnHandlers): Column<Employee>[] => [
  { id: "name", label: "Name", isSortable: true },
  { id: "department", label: "Department", isSortable: true },
  {
    id: "actions",
    cell: ({ row }) => [
      h(Button, { variant: "ghost", size: "sm", onClick: () => handlers.onEdit(row.original) }, () => "Edit"),
      h(Button, { variant: "destructive", size: "sm", onClick: () => handlers.onDelete(row.original) }, () => "Delete"),
    ],
  },
];
```

Rules for valid JSON strings:
- Newlines inside strings MUST be written as `\n` (backslash + n), NOT as actual line breaks
- Double quotes inside strings MUST be escaped as `\"`
- Backtick characters do NOT need escaping

WRONG — text before the JSON block will be rejected:
```
Here is my implementation... I will now write the component.
```json
{ "name": "write_file", ... }
```
```

CORRECT — the JSON code block is the entire response, nothing else.
