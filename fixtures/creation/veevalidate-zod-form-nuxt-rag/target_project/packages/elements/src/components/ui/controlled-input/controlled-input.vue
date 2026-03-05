<script setup lang="ts" generic="T">
import type { ControlledInputProps } from "./type";
import { FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '../form';
import { InputGroup } from "../input-group";

defineProps<ControlledInputProps<T>>();

defineEmits<{
  (e: "inputClick"): void;
  (e: "update:modelValue", payload: T): void;
}>();
</script>

<template>
  <FormField :id="name" v-slot="{ componentField }" :name="name">
    <FormItem>
      <FormLabel :disabled="disabled">{{ label }}</FormLabel>
      <FormControl>
        <InputGroup
          :placeholder="placeholder"
          :disabled="disabled"
          :addOnText="addOnText"
          :defaultValue="defaultValue"
          :modelValue="modelValue"
          v-bind="componentField"
          :type="type || 'text'"
          @click="$emit('inputClick')"
          @update:model-value="(value: T) => $emit('update:modelValue', value)"
          :name="name"
        >
          <template v-if="$slots.inputIconLeft" #iconLeft>
            <slot name="inputIconLeft"></slot>
          </template>
          <template v-if="$slots.inputCustomAddOn" #customAddOn>
            <slot name="inputCustomAddOn"></slot>
          </template>
          <template v-if="$slots.inputIconRight" #iconRight>
            <slot name="inputIconRight"></slot>
          </template>
        </InputGroup>
      </FormControl>
      <FormMessage />
      <FormDescription>
        {{ description }}
      </FormDescription>
    </FormItem>
  </FormField>
</template>
