<script setup lang="ts">
// This component has TypeScript errors. Fix them.

interface ButtonProps {
  label: string
  count: string
  disabled: boolean
}

const props = defineProps<ButtonProps>()

const doubled = computed(() => props.count * 2)
</script>

<template>
  <button :disabled="props.disabled">
    {{ props.label }} ({{ doubled }})
  </button>
</template>
