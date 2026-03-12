<script setup lang="ts">
import OrdersDataTable from "./orders/OrdersDataTable.vue";
import RegistrationForm from "./registration/components/RegistrationForm.vue";
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-8">
    <RegistrationForm />
    <OrdersDataTable />
  </div>
</template>
