<script setup lang="ts" generic="TData, TValue">
import type {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  ExpandedState,
} from "@tanstack/vue-table";

import {
  FlexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  getExpandedRowModel,
  useVueTable,
} from "@tanstack/vue-table";

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { valueUpdater } from "@/lib/utils";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
// import { Button, Input, Loading } from "@/components/atoms";
import { ref } from "vue";
import type { Config, DataTableStatus } from "./types";
import { Button } from "../button";
import { Input } from "../input";
import { Loading } from "../loading";

interface DataTableProps {
  data: TData[];
  columns: ColumnDef<TData, TValue>[];
  config?: Config<Extract<keyof TData, string>>;
  status?: DataTableStatus;
  errorMessage?: string;
}

const props = defineProps<DataTableProps>();

const sorting = ref<SortingState>([]);
const columnFilters = ref<ColumnFiltersState>([]);
const columnVisibility = ref<VisibilityState>({});
const rowSelection = ref({});
const expanded = ref<ExpandedState>({});
const {
  filter = true,
  filterModel,
  filterPlaceholder,
  pagination = true,
  hideColumns = true,
  manualSorting = false,
  onSortChange,
} = props?.config || {};

const table = useVueTable({
  get data() {
    return props.data;
  },
  get columns() {
    return props.columns;
  },
  getCoreRowModel: getCoreRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  getSortedRowModel: manualSorting ? undefined : getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  getExpandedRowModel: getExpandedRowModel(),
  manualSorting,
  onSortingChange: (updaterOrValue) => {
    valueUpdater(updaterOrValue, sorting);
    if (manualSorting && onSortChange) {
      onSortChange(sorting.value);
    }
  },
  onColumnFiltersChange: (updaterOrValue) =>
    valueUpdater(updaterOrValue, columnFilters),
  onColumnVisibilityChange: (updaterOrValue) =>
    valueUpdater(updaterOrValue, columnVisibility),
  onRowSelectionChange: (updaterOrValue) =>
    valueUpdater(updaterOrValue, rowSelection),
  onExpandedChange: (updaterOrValue) => valueUpdater(updaterOrValue, expanded),
  state: {
    get sorting() {
      return sorting.value;
    },
    get columnFilters() {
      return columnFilters.value;
    },
    get columnVisibility() {
      return columnVisibility.value;
    },
    get rowSelection() {
      return rowSelection.value;
    },
    get expanded() {
      return expanded.value;
    },
  },
});

const isSelectionActive = !!table
  .getHeaderGroups()
  .map((value) => value.headers)
  .flat()
  .find((element) => element.id === "select");
</script>

<template>
  <div class="border rounded-md px-4">
    <div class="flex items-center py-4">
      <Input
        v-if="filter && filterModel"
        class="max-w-sm"
        :placeholder="filterPlaceholder || 'Filtra...'"
        :model-value="table.getColumn(filterModel)?.getFilterValue() as string"
        @update:model-value="
          table.getColumn(filterModel)?.setFilterValue($event)
        "
      />
      <DropdownMenu v-if="hideColumns">
        <DropdownMenuTrigger as-child>
          <Button variant="secondary" class="ml-auto">
            [[ ___Columns___ ]]
            <ChevronDown class="w-4 h-4 ml-2" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuCheckboxItem
            v-for="column in table
              .getAllColumns()
              .filter(
                (column) => column.getCanHide() && column.id !== 'actions'
              )"
            :key="column.id"
            class="capitalize"
            :model-value="column.getIsVisible()"
            @update:model-value="
              (value) => {
                column.toggleVisibility(!!value);
              }
            "
          >
            {{ column.id }}
          </DropdownMenuCheckboxItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
    <div>
      <Table>
        <TableHeader>
          <TableRow
            v-for="headerGroup in table.getHeaderGroups()"
            :key="headerGroup.id"
          >
            <TableHead v-for="header in headerGroup.headers" :key="header.id">
              <FlexRender
                v-if="!header.isPlaceholder"
                :render="header.column.columnDef.header"
                :props="header.getContext()"
              />
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <template v-if="status === 'loading'">
            <TableRow>
              <TableCell :colspan="columns.length" class="h-24 text-center">
                <Loading />
              </TableCell>
            </TableRow>
          </template>
          <template v-else-if="status === 'error'">
            <TableRow>
              <TableCell :colspan="columns.length" class="h-24 text-center">
                <div class="text-destructive">
                  {{
                    errorMessage ||
                    "Si è verificato un errore nel caricamento dei dati."
                  }}
                </div>
              </TableCell>
            </TableRow>
          </template>
          <template
            v-else-if="status === 'empty' || !table.getRowModel().rows?.length"
          >
            <TableRow>
              <TableCell :colspan="columns.length" class="h-24 text-center">
                [[ ___No results.___ ]]
              </TableCell>
            </TableRow>
          </template>
          <template v-else>
            <template v-for="row in table.getRowModel().rows" :key="row.id">
              <TableRow
                :data-state="row.getIsSelected() ? 'selected' : undefined"
              >
                <TableCell v-for="cell in row.getVisibleCells()" :key="cell.id">
                  <FlexRender
                    :render="cell.column.columnDef.cell"
                    :props="cell.getContext()"
                  />
                </TableCell>
              </TableRow>
              <TableRow v-if="row.getIsExpanded()">
                <TableCell :colspan="row.getAllCells().length">
                  {{ JSON.stringify(row.original) }}
                </TableCell>
              </TableRow>
            </template>
          </template>
        </TableBody>
      </Table>
    </div>
    <div class="flex items-center justify-end py-4 space-x-2">
      <div
        v-if="isSelectionActive"
        class="flex-1 text-sm text-muted-foreground"
      >
        {{ table.getFilteredSelectedRowModel().rows.length }} of
        {{ table.getFilteredRowModel().rows.length }} row(s) selected.
      </div>
      <div v-if="pagination" class="space-x-2">
        <Button
          variant="secondary"
          :disabled="!table.getCanPreviousPage()"
          @click="table.previousPage()"
        >
          [[ ___Previous___ ]]
        </Button>
        <Button
          variant="secondary"
          :disabled="!table.getCanNextPage()"
          @click="table.nextPage()"
        >
          [[ ___Next___ ]]
        </Button>
      </div>
    </div>
  </div>
</template>
