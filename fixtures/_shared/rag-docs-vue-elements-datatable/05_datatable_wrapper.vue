<!--
  EXAMPLE: Complete DataTable wrapper component with action handlers as props.

  Pattern:
  - defineProps with typed handler callbacks (onView, onCancel)
  - Call createColumns(handlers) factory with props — returns Column<Order>[]
  - Import data from a sibling file
  - Pass columns, data, config to <DataTable>
  - config.filterModel must match a column id
-->
<script setup lang="ts">
import { DataTable } from "elements";
import { createColumns } from "./columns";
import { orders } from "./data";
import type { Order } from "./types";

// Receive action handlers as props — typed with the Order interface
const props = defineProps<{
  onView: (order: Order) => void;
  onCancel: (order: Order) => void;
}>();

// Create columns with handlers captured in closure
const columns = createColumns({
  onView: props.onView,
  onCancel: props.onCancel,
});
</script>

<template>
  <!--
    filter: true enables the search box
    filterModel: "customer" filters by the customer column
  -->
  <DataTable
    :columns="columns"
    :data="orders"
    :config="{ filter: true, filterModel: 'customer' }"
  />
</template>
