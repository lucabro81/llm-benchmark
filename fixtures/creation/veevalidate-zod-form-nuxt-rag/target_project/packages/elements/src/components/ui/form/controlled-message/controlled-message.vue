<script setup lang="ts">
import { computed } from "vue";
import { useFieldError } from "vee-validate";
import { Input } from "../../input";
import { FormControl, FormField, FormItem, FormMessage } from "..";

const error = useFieldError("global");
const hasError = computed(() => !!error.value);
</script>
<template>
  <FormField v-slot="{ componentField }" name="global">
    <FormItem v-if="hasError">
      <FormControl>
        <Input type="hidden" v-bind="componentField" />
        <FormMessage />
      </FormControl>
    </FormItem>
  </FormField>
</template>
