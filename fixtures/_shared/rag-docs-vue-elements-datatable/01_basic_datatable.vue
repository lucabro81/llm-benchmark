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
  { id: "3", name: "Clara", email: "clara@example.com", role: "user" },
];

// Plain text columns — no cell renderer needed, DataTable uses the field value directly
const columns: Column<User>[] = [
  {
    id: "name",
    label: "Name",
    isSortable: true,
  },
  {
    id: "email",
    label: "Email",
    isSortable: true,
  },
  {
    id: "role",
    label: "Role",
    isSortable: false,
  },
];
</script>

<template>
  <!--
    :columns — Column<T>[] array, required
    :data    — T[] array, required
    :config  — optional; filter: true + filterModel enables search box on specified column
  -->
  <DataTable
    :columns="columns"
    :data="users"
    :config="{ filter: true, filterModel: 'name' }"
  />
</template>
