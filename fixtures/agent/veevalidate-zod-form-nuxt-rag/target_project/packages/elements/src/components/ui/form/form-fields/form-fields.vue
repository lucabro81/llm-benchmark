<script setup lang="ts">
import type { FormContext } from "vee-validate";
import { inject } from "vue";
import { ControlledMessage } from "../controlled-message";

/**
 * Form Fields Component
 *
 * Wrapper component for form fields that provides access to form context and error handling
 * via scoped slot. Must be used as a child of the Form component.
 * See: packages/elements/src/components/organisms/cmp/form/form.vue
 *
 * Scoped Slot Props:
 * @slot default
 * @slot-prop {FormContext} form - The vee-validate form context instance
 * @slot-prop {() => void} resetGeneralError - Function to reset general form errors
 *
 * Example:
 * ```html
 * <CmpFormFields v-slot="{ form, resetGeneralError }">
 *   <CmpControlledInput
 *     name="email"
 *     label="Email"
 *     placeholder="inserisci email"
 *   />
 *   <CmpControlledInputPassword
 *     name="password"
 *     label="Password"
 *     placeholder="inserisci password"
 *   />
 * </CmpFormFields>
 * ```
 */
const form =
  inject<FormContext<Record<string, unknown>, Record<string, unknown>>>("form");
const resetGeneralError = inject<() => void>("resetGeneralError");
</script>

<template>
  <slot :form="form" :reset-general-error="resetGeneralError" />
  <ControlledMessage />
</template>
