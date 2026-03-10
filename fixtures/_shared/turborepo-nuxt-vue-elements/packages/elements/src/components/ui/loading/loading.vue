<script setup lang="ts">
import RingSpinner from './ring-spinner.vue';


defineProps<{
  size?: number;
}>();
</script>

<template>
  <div
    data-testid="loading"
    class="flex justify-center align-middle w-full h-full"
  >
    <RingSpinner
      :width="size?.toString() || '80'"
      :height="size?.toString() || '80'"
    />
  </div>
</template>
