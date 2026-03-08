<template>
  <div class="score-bar">
    <div class="score-bar__track">
      <div
        class="score-bar__fill"
        :style="{ width: `${score * 10}%`, backgroundColor: color }"
      />
    </div>
    <span class="score-bar__value">{{ (props.score ?? 0).toFixed(1) }}</span>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{ score: number }>(), { score: 0 })

const color = computed(() => {
  if (props.score >= 8) return 'var(--color-score-great)'
  if (props.score >= 6) return 'var(--color-score-good)'
  if (props.score >= 3) return 'var(--color-score-mid)'
  return 'var(--color-score-low)'
})
</script>

<style scoped>
.score-bar {
  display: flex;
  align-items: center;
  gap: .5rem;
  min-width: 120px;
}
.score-bar__track {
  flex: 1;
  height: 8px;
  background: var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}
.score-bar__fill {
  height: 100%;
  border-radius: 4px;
  transition: width .3s ease;
}
.score-bar__value {
  font-size: .85rem;
  font-weight: 600;
  width: 2.5rem;
  text-align: right;
  flex-shrink: 0;
}
</style>
