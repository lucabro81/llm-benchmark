You are implementing a Vue 3 data table component in a Turborepo monorepo.

## Task

Implement two files for an orders data table:

1. **`apps/web/src/orders/columns.ts`** — column definitions factory
2. **`apps/web/src/orders/OrdersDataTable.vue`** — wrapper component

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

### `columns.ts` must export

```ts
export const createColumns = (handlers: OrderColumnHandlers): Column<Order>[] => [ ... ]
```

Where `OrderColumnHandlers` is imported from `./types`:
```ts
import type { Order, OrderStatus, OrderColumnHandlers } from "./types";
```

### `OrdersDataTable.vue` props

`onView` and `onCancel` are optional — the component is rendered as `<OrdersDataTable />` with no props in `app.vue`. Use `withDefaults`:

```ts
const props = withDefaults(defineProps<{
  onView?: (order: Order) => void;
  onCancel?: (order: Order) => void;
}>(), {
  onView: () => {},
  onCancel: () => {},
})
```

## How to use your tools

Use `write_file` + `run_compilation` for each file:
- `write_file` only writes the file and returns `"File written."` — it does NOT compile
- After writing both files, call `run_compilation` to get TypeScript feedback
- Fix any errors reported and repeat until compilation succeeds
- `apps/web/src/orders/types.ts` and `apps/web/src/orders/data.ts` already exist — do NOT write them

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
  price: number;
  releaseDate: string;
}

export const columns: Column<Product>[] = [
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
      return h("span", {}, formatted);
    },
  },
];
```

### 03_status_badge.ts

```ts
/**
 * EXAMPLE: Status badge column using Record<Status, string> lookup maps.
 */
import type { Column } from "elements";
import { h } from "vue";

type ItemStatus = "active" | "inactive" | "pending";

const statusLabels: Record<ItemStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  pending: "Pending",
};

const statusClasses: Record<ItemStatus, string> = {
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-800",
  pending: "bg-yellow-100 text-yellow-800",
};

export const columns: Column<{ id: string; status: ItemStatus }>[] = [
  {
    id: "status",
    label: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as ItemStatus;
      return h("span", { class: statusClasses[status] }, statusLabels[status]);
    },
  },
];
```

### 04_action_columns.ts

```ts
/**
 * EXAMPLE: Action column with createColumns(handlers) factory pattern.
 *
 * - Export createColumns(handlers): Column<T>[] factory
 * - h(Button, { onClick: () => handlers.fn(row.original) }, () => "Label")
 * - row.original gives typed access to the full row data object
 * - Import Button from "elements"
 * - id: "actions" — DataTable auto-adds flex layout
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

### 05_datatable_wrapper.vue

```vue
<!--
  EXAMPLE: Complete DataTable wrapper component with optional action handler props.

  Pattern:
  - withDefaults(defineProps<{ onView?, onCancel? }>(), { ... }) for optional callbacks
  - Call createColumns(handlers) factory with props
  - Import data from a sibling file
  - Pass columns, data, config to <DataTable>
-->
<script setup lang="ts">
import { DataTable } from "elements";
import { createColumns } from "./columns";
import { orders } from "./data";
import type { Order } from "./types";

const props = withDefaults(defineProps<{
  onView?: (order: Order) => void;
  onCancel?: (order: Order) => void;
}>(), {
  onView: () => {},
  onCancel: () => {},
});

const columns = createColumns({
  onView: props.onView,
  onCancel: props.onCancel,
});
</script>

<template>
  <DataTable
    :columns="columns"
    :data="orders"
    :config="{ filter: true, filterModel: 'customer' }"
  />
</template>
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
