import type { CellContext, SortingState } from "@tanstack/vue-table";
import type { VNode } from "vue";

export type DataTableStatus = "loading" | "error" | "empty" | "success";

export type Config<T extends string> = (
  { filter: boolean, filterModel: T } |
  { filter?: never, filterModel?: never }
) &
{
  filterPlaceholder?: string
  rowsCheckable?: boolean;
  hideColumns?: boolean,
  pagination?: boolean,
  hideActions?: boolean,
  manualSorting?: boolean,
  onSortChange?: (sortingState: SortingState) => void | Promise<void>
}

export interface TableAction<T> {
  [key: string]: (data: T) => void;
}

export interface Column<T> {
  id: string;
  label?: (() => VNode | VNode[]) | string;
  isSortable?: boolean;
  initialSort?: 'asc' | 'desc';
  skipUnordered?: boolean;
  cell?: (props: CellContext<T, unknown>) => VNode | VNode[];
}