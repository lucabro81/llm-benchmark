<script setup lang="ts">
import PaymentsDataTable from "./payments/PaymentsDataTable.vue";
import RegistrationForm from "./registration/components/RegistrationForm.vue";
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-8">
    <RegistrationForm />
    <PaymentsDataTable />
  </div>
</template>
