<script setup lang="ts">
import { DataTable } from 'elements';
import { columns } from "./columns";
import { payments } from "./data";

</script>

<template>
  <DataTable :columns="columns" :data="payments" :config="{filter: true, filterModel: 'email'}" />
</template>
