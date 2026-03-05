<script setup lang="ts">
import type { AcceptableValue } from 'reka-ui';
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '../form';
import { RadioGroup, RadioGroupItem } from '../radio-group';

type RadioOption = { value: string; label: string };

withDefaults(
  defineProps<{
    name: string;
    label: string;
    options: RadioOption[];
    orientation?: "horizontal" | "vertical";
  }>(),
  {
    orientation: "vertical",
  }
);

defineEmits<{
  (e: "inputClick"): void;
  (e: "update:modelValue", payload: AcceptableValue): void;
}>();
</script>
<template>
  <FormField :id="name" v-slot="{ componentField }" :name="name">
    <FormItem>
      <FormLabel>{{ label }}</FormLabel>
      <FormControl>
        <RadioGroup
          v-bind="componentField"
          class="flex flex-col space-y-1"
          :class="{
            'flex-col': orientation === 'vertical',
            'flex-row space-x-3': orientation === 'horizontal',
          }"
          @update:model-value="(value) => $emit('update:modelValue', value)"
          @click="$emit('inputClick')"
        >
          <slot v-for="option in options" name="item" :option="option">
            <FormItem class="flex items-center">
              <FormControl>
                <RadioGroupItem :value="option.value" />
              </FormControl>
              <FormLabel class="font-normal">
                {{ option.label }}
              </FormLabel>
            </FormItem>
          </slot>
        </RadioGroup>
      </FormControl>
      <FormMessage />
    </FormItem>
  </FormField>
</template>
