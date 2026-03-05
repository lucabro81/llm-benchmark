<script setup lang="ts">
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '../form';
import { Textarea } from '../textarea';



defineOptions({
  inheritAttrs: false,
});

defineProps<{
  name: string;
  label: string;
  placeholder: string;
}>();

defineEmits<{
  (e: "inputClick"): void;
  (e: "update:modelValue", payload: string | number): void;
}>();
</script>
<template>
  <FormField :id="name" v-slot="{ componentField }" :name="name">
    <FormItem>
      <FormLabel>{{ label }}</FormLabel>
      <FormControl>
        <Textarea
          :placeholder="placeholder"
          v-bind="{ ...$attrs, ...componentField }"
          @click="$emit('inputClick')"
          @update:model-value="(value) => $emit('update:modelValue', value)"
        />
      </FormControl>
      <FormMessage />
    </FormItem>
  </FormField>
</template>
