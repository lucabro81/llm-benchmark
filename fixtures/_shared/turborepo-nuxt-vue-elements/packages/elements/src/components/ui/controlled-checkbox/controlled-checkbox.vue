<script setup lang="ts">
import { Checkbox } from '../checkbox';
import { FormControl, FormDescription, FormField, FormItem, FormLabel } from '../form';


interface ControlledCheckboxProps {
  name: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

defineProps<ControlledCheckboxProps>();

defineEmits<{
  (e: "inputClick"): void;
  (e: "update:modelValue", payload: string | boolean): void;
}>();
</script>
<template>
  <FormField
    :id="name"
    v-slot="{ value, handleChange }"
    type="checkbox"
    :name="name"
  >
    <FormItem>
      <div class="flex items-center gap-x-3">
        <FormControl>
          <Checkbox
            :model-value="value"
            :disabled="disabled"
            @update:model-value="handleChange"
            @click="$emit('inputClick')"
          />
        </FormControl>
        <div class="space-y-0.5">
          <FormLabel>{{ label }}</FormLabel>
          <FormDescription v-if="description">
            {{ description }}
          </FormDescription>
        </div>
      </div>
      <FormMessage />
    </FormItem>
  </FormField>
</template>
