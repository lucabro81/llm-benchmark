<template>
  <nav class="breadcrumb" aria-label="breadcrumb">
    <template v-for="(item, i) in items" :key="i">
      <NuxtLink v-if="item.to" :to="item.to" class="breadcrumb__link">{{ item.label }}</NuxtLink>
      <span v-else class="breadcrumb__current">{{ item.label }}</span>
      <span v-if="i < items.length - 1" class="breadcrumb__sep" aria-hidden="true"> / </span>
    </template>
  </nav>
</template>

<script setup lang="ts">
defineProps<{
  items: Array<{ label: string; to?: string }>
}>()
</script>

<style scoped>
.breadcrumb {
  font-size: .85rem;
  margin-bottom: 1.5rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0;
}
.breadcrumb__link {
  color: var(--color-text-muted);
  text-decoration: none;
}
.breadcrumb__link:hover {
  color: var(--color-accent);
}
.breadcrumb__current {
  color: var(--color-text);
  font-weight: 500;
}
.breadcrumb__sep {
  color: var(--color-border);
  padding: 0 .2rem;
}
</style>
