import type { CellContext, ColumnDef, HeaderContext, SortDirection } from "@tanstack/vue-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-vue-next";
import { h, ref } from "vue";
import type { Column } from "./types";
import { Checkbox } from "../checkbox";
import { Button } from "../button";

function checkColumn<T>(): ColumnDef<T> {
  return {
    id: 'select',
    header: ({ table }: HeaderContext<T, unknown>) => h(Checkbox, {
      'modelValue': table.getIsAllPageRowsSelected(),
      // TODO: verify that "indeterminate"
      'onUpdate:modelValue': (value: boolean | "indeterminate") => table.toggleAllPageRowsSelected(!!value),
      'ariaLabel': 'Select all',
    }),
    cell: ({ row }: CellContext<T, unknown>) => h(Checkbox, {
      'modelValue': row.getIsSelected(),
      'onUpdate:modelValue': (value: boolean | "indeterminate") => row.toggleSelected(!!value),
      'ariaLabel': 'Select row',
    }),
    enableSorting: false,
    enableHiding: false,
  }
}

function normalColumns<T>(columns: Column<T>[]): ColumnDef<T>[] {

  return columns.map((col) => {
    return {
      accessorKey: col.id,
      header: ({ column }: HeaderContext<T, unknown>) => {
        if (!colOrder.value[col.id]) {
          // if none is set, set to initialSort (Asc or Desc)
          colOrder.value[col.id] = colOrder.value[col.id] || (col.initialSort || 'none') as SortDirection;
          // apply initial sort to column
          if (col.initialSort) {
            column.toggleSorting(col.initialSort === 'desc')
          }
        }
        if (col.isSortable) {
          return h(Button, {
            onClick: () => {
              if (colOrder.value[col.id] === "desc" && !col.skipUnordered) {
                column.clearSorting();
                colOrder.value[col.id] = 'none';
              }
              else {
                column.toggleSorting(column.getIsSorted() === 'asc')
                colOrder.value[col.id] = column.getIsSorted() || 'none';
              }
            },
          }, { icon: h(orderIconObj[colOrder.value[col.id] || "asc"]), default: col.label })
        }

        if (typeof (col.label) === "string") {
          return h('div', {}, col.label);
        }

        return col.label?.();
      },
      cell: (props: CellContext<T, unknown>) =>
        h('div', col.id === "actions" ? { class: "flex justify-end gap-2" } : {}, col?.cell?.(props) ?? props.row.getValue(col.id)),
    }
  })
}

const colOrder = ref<{ [id: string]: 'none' | SortDirection }>({});
const orderIconObj = {
  asc: ArrowUp,
  desc: ArrowDown,
  none: ArrowUpDown
}

export function useColumns<T>(columns: Column<T>[], checkColumnIsNeeded = false): ColumnDef<T>[] {
  let completeColumns: ColumnDef<T>[] = [];

  if (checkColumnIsNeeded) {
    completeColumns = completeColumns.concat([checkColumn()])
  }

  return completeColumns
    .concat(normalColumns(columns));

}