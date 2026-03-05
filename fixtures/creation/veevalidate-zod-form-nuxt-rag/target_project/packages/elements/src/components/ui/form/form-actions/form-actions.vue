<script setup lang="ts" generic="P extends Record<string, any>">
import type { FormContext } from "vee-validate";
import type { ActionsForm } from "../form/types";
import { inject } from "vue";

/**
 * Form Actions Component
 *
 * Wrapper component for form actions (buttons, links, etc.) that provides access to
 * form state and actions via scoped slot. Must be used as a child of the Form component.
 * See: packages/elements/src/components/organisms/cmp/form/form.vue
 *
 * Scoped Slot Props:
 * @slot default
 * @slot-prop {FormContext} form - The vee-validate form context instance
 * @slot-prop {ActionsForm<P>} actions - Object containing all actions passed to the form (including onSubmit)
 * @slot-prop {boolean} isValid - Boolean indicating if the form is valid
 *
 * Example:
 * ```html
 * <CmpFormActions v-slot="{ form, actions, isValid }">
 *   <CmpButton
 *     type="button"
 *     variant="ghost"
 *     @click="actions.forgotPassword"
 *   >
 *     Password dimenticata?
 *   </CmpButton>
 *   <CmpButton
 *     :disabled="!isValid || form.isSubmitting.value"
 *     :loading="form.isSubmitting.value"
 *   >
 *     Accedi
 *   </CmpButton>
 * </CmpFormActions>
 * ```
 */
const form =
  inject<FormContext<Record<string, unknown>, Record<string, unknown>>>("form");
const actions = inject<ActionsForm<P>>("actions");
const isValid = inject<boolean>("isValid");
</script>
<template>
  <div>
    <slot :form="form" :actions="actions" :is-valid="isValid" />
  </div>
</template>
