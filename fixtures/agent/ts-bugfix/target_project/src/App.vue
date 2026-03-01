<script setup lang="ts">
import BuggyComponent from './components/BuggyComponent.vue'
</script>

<template>
  <BuggyComponent label="Click me" :count="0" :disabled="false" />
</template>
