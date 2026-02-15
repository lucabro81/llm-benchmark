<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: String,
  count: Number,
  items: Array
})

const doubled = computed(() => props.count * 2)
</script>

<template>
  <div>
    <h1>{{ title }}</h1>
    <p>Count: {{ count }}, Doubled: {{ doubled }}</p>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
  </div>
</template>
