<script setup lang="ts" generic="P extends Record<string, any>">
import { useCustomForm } from "@/lib/forms";
import { useForm } from "vee-validate";
import type { z } from "zod";
import { toTypedSchema } from "@vee-validate/zod";
import { computed, provide, watch } from "vue";
import type { ActionsForm } from "./types";

/**
 * Form Component
 *
 * A form component that handles validation and submission using Zod schema validation.
 * The Form component is composed of three main elements:
 * 1. Form - The main component that manages form state and validation
 * 2. FormFields - Wrapper component for form fields (provides form context and resetGeneralError)
 *    See: packages/elements/src/components/organisms/cmp/form-fields/form-fields.vue
 * 3. FormActions - Wrapper component for form actions (provides form, actions, and isValid)
 *    See: packages/elements/src/components/organisms/cmp/form-actions/form-actions.vue
 *
 * Example:
 * ```html
 * <CmpForm
 *   :initialValues="{ email: '', password: '' }"
 *   :actions="{ onSubmit: async (values) => values, forgotPassword: () => {} }"
 *   :formSchema="zodFormSchema"
 * >
 *   <CmpFormFields v-slot="{ resetGeneralError }">
 *     <CmpControlledInput name="email" label="Email" placeholder="inserisci email" />
 *     <CmpControlledInputPassword name="password" label="Password" placeholder="inserisci password" />
 *   </CmpFormFields>
 *
 *   <CmpFormActions v-slot="{ form, actions, isValid }">
 *     <CmpButton type="button" variant="ghost" @click="actions.forgotPassword">
 *       Password dimenticata?
 *     </CmpButton>
 *     <CmpButton :disabled="!isValid || form.isSubmitting.value" :loading="form.isSubmitting.value">
 *       Accedi
 *     </CmpButton>
 *   </CmpFormActions>
 * </CmpForm>
 * ```
 */
const props = defineProps<{
  /** The initial values of the form fields */
  initialValues: P;
  /** An object containing the action needed to the buttons in the action slot. onSubmit is required for form submission */
  actions: ActionsForm<P>;
  /** The Zod schema for form validation */
  formSchema: z.ZodObject<any>;
  /** Whether to validate on blur event */
  validateOnBlur?: boolean;
}>();

const FormSchema = computed(() => toTypedSchema(props.formSchema));

const form = useForm<z.infer<typeof props.formSchema>>({
  validationSchema: FormSchema,
  initialValues: props.initialValues,
});

// Set the global field, which is used for displaying general error messages
// and is not a user-editable field.
form.setFieldValue("global", undefined);

const isValid = computed(() => form.meta.value.valid);

watch(
  () => props.initialValues,
  (newValues) => {
    for (const [key, value] of Object.entries(newValues)) {
      form.setFieldValue(key, value);
    }
  },
  { deep: true },
);

const { onSubmit, resetGeneralError } = useCustomForm<P>(
  form,
  props.actions.onSubmit,
);

provide("form", form);
provide("resetGeneralError", resetGeneralError);
provide("actions", props.actions);
provide("isValid", isValid);
</script>
<template>
  <form class="space-y-4" @submit="onSubmit">
    <slot />
  </form>
</template>
