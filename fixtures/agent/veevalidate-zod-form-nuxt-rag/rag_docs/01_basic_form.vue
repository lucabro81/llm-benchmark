<!--
  EXAMPLE: Basic form with ControlledInput, ControlledCheckbox, and Button.

  Pattern:
  - Import Form, FormFields, FormActions, controlled components and Button from "elements"
  - <Form> takes :initial-values, :form-schema (Zod schema), :actions ({ onSubmit })
  - <FormFields v-slot="{ form, resetGeneralError }"> wraps all input components
  - <FormActions v-slot="{ form, isValid }"> wraps the submit button
  - Pass @input-click="resetGeneralError" to each controlled component
-->
<script setup lang="ts">
import { Button, ControlledCheckbox, ControlledInput, Form, FormActions, FormFields } from "elements";
import { z } from "zod";

const loginSchema = z.object({
  email: z.string().email("Formato email non valido").min(1, "Email obbligatoria"),
  password: z.string().min(1, "Password obbligatoria"),
  rememberMe: z.boolean().optional(),
});

type LoginFormValues = z.infer<typeof loginSchema>;

// initial-values must include ALL schema fields
const initialValues: LoginFormValues = {
  email: "",
  password: "",
  rememberMe: false,
};

const { onSubmit } = defineProps<{
  onSubmit: (values: LoginFormValues) => Promise<LoginFormValues>;
}>();

const actions = { onSubmit };
</script>

<template>
  <div class="w-full">
    <Form :initial-values="initialValues" :form-schema="loginSchema" :actions="actions">

      <FormFields v-slot="{ resetGeneralError }">
        <ControlledInput
          name="email"
          label="Email"
          placeholder="inserisci email"
          @input-click="resetGeneralError"
        />
        <ControlledInput
          type="password"
          name="password"
          label="Password"
          placeholder="inserisci password"
          @input-click="resetGeneralError"
        />
        <!-- name must exactly match the key in the Zod schema -->
        <ControlledCheckbox
          name="rememberMe"
          label="Ricordami"
          @input-click="resetGeneralError"
        />
      </FormFields>

      <FormActions v-slot="{ form, isValid }" class="mt-6">
        <Button
          type="submit"
          class="w-full"
          :disabled="!isValid || form?.isSubmitting.value"
        >
          Accedi
        </Button>
      </FormActions>

    </Form>
  </div>
</template>
