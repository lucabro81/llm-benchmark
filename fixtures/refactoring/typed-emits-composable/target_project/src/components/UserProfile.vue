<script setup>
import { computed } from 'vue'

const props = defineProps({
  user: Object,
  editable: Boolean
})

const emit = defineEmits(['update:user', 'delete'])

const displayName = computed(() => {
  return props.user?.name || 'Unknown User'
})

function handleUpdate() {
  emit('update:user', props.user)
}

function handleDelete() {
  emit('delete', props.user?.id)
}
</script>

<template>
  <div class="user-profile">
    <h2>{{ displayName }}</h2>
    <p>{{ user?.email }}</p>
    <p>Role: {{ user?.role }}</p>
    <button v-if="editable" @click="handleUpdate">Update</button>
    <button v-if="editable" @click="handleDelete">Delete</button>
  </div>
</template>
