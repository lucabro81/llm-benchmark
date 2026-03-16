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

Where `OrderColumnHandlers` is imported from `./types`.

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

You have three tools: `write_file`, `run_compilation`, and `query_rag`.

- Use `query_rag` FIRST to look up the DataTable component API and usage examples
- Use `write_file` to write the files (returns `"File written."` — does NOT compile)
- Use `run_compilation` to check for TypeScript errors after writing
- Fix errors and repeat until compilation succeeds

**`apps/web/src/orders/types.ts`** and **`apps/web/src/orders/data.ts`** already exist — do NOT write them.

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
