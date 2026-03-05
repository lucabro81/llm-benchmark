<!--
  EXAMPLE: Checkbox that conditionally shows another field.

  Pattern:
  - FormFields slot exposes `form` (vee-validate FormContext)
  - form.values.<fieldName> gives the current reactive value of any field
  - Use v-if on a sibling component to show/hide based on another field's value
-->
<script setup lang="ts">
import { Button, ControlledCheckbox, ControlledInput, Form, FormActions, FormFields } from "elements";
import { z } from "zod";

const schema = z.object({
  hasAlternateEmail: z.boolean().optional(),
  // alternateEmail is optional in Zod; required logic handled in UI or via refine
  alternateEmail: z.string().email("Email non valida").optional(),
});

type FormValues = z.infer<typeof schema>;

const initialValues: FormValues = {
  hasAlternateEmail: false,
  alternateEmail: "",
};

const actions = {
  onSubmit: async (values: FormValues) => values,
};
</script>

<template>
  <Form :initial-values="initialValues" :form-schema="schema" :actions="actions">

    <FormFields v-slot="{ form, resetGeneralError }">
      <ControlledCheckbox
        name="hasAlternateEmail"
        label="Ho un'email alternativa"
        @input-click="resetGeneralError"
      />

      <!--
        form.values is the reactive vee-validate FormContext values object.
        v-if re-evaluates automatically whenever the checkbox changes.
      -->
      <ControlledInput
        v-if="form.values.hasAlternateEmail"
        name="alternateEmail"
        label="Email alternativa"
        type="email"
        placeholder="altra@email.com"
        @input-click="resetGeneralError"
      />
    </FormFields>

    <FormActions v-slot="{ form, isValid }">
      <Button type="submit" :disabled="!isValid || form?.isSubmitting.value">
        Salva
      </Button>
    </FormActions>

  </Form>
</template>
