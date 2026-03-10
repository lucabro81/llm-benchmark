<script setup lang="ts" generic="T">
import { ref, computed, watch, type Ref } from "vue";
import DataTableBase from "./data-table-base.vue";
import { useColumns } from "./columns";
import type { Column, Config, DataTableStatus } from "./types";

const props = withDefaults(
  defineProps<{
    data?: T[] | (() => Promise<T[]>) | null;
    columns: Column<T>[];
    config?: Config<Extract<keyof T, string>>;
    status?: DataTableStatus;
    errorMessage?: string;
  }>(),
  {
    config: () => ({}),
  }
);

const datatableColumns = useColumns(
  props.columns,
  props?.config?.rowsCheckable || false
);

const loadedData = ref<T[]>([]) as Ref<T[]>;
const isLoading = ref(false);
const error = ref<Error | null>(null);

const computedStatus = computed<DataTableStatus>(() => {
  if (props.status) return props.status;

  if (isLoading.value) return "loading";
  if (error.value) return "error";
  if (loadedData.value.length === 0) return "empty";
  return "success";
});

const computedErrorMessage = computed(() => {
  return props.errorMessage || error.value?.message || undefined;
});

const extractionData = async () => {
  isLoading.value = true;
  error.value = null;
  try {
    loadedData.value = await (props.data as () => Promise<T[]>)();
  } catch (err) {
    error.value = err instanceof Error ? err : new Error(String(err));
    loadedData.value = [];
  } finally {
    isLoading.value = false;
  }
};

const loadData = () => {
  if (!props.data) {
    loadedData.value = [];
  } else if (typeof props.data === "function") {
    extractionData();
  } else {
    loadedData.value = props.data;
  }
};

// Caricamento iniziale
loadData();

// Watch per reagire ai cambiamenti della prop data quando gestita esternamente
watch(() => props.data, (newData) => {
  if (newData && typeof newData !== "function") {
    loadedData.value = newData;
  }
}, { deep: true });
</script>
<template>
  <DataTableBase
    :columns="datatableColumns"
    :data="loadedData"
    :config="config"
    :status="computedStatus"
    :error-message="computedErrorMessage"
  />
</template>
