<script setup lang="ts">
import { Button, ControlledCheckbox, ControlledInput, Form, FormActions, FormFields } from "elements";
import { loginFormSchema, type LoginFormValues } from "../types";

const { onSubmit } = defineProps<{
  onSubmit: (values: LoginFormValues) => Promise<LoginFormValues>;
}>();

const initialValues: LoginFormValues = {
  email: "",
  password: "",
  rememberMe: false,
};

const actions = {
  onSubmit,
};
</script>

<template>
  <div class="w-full">
    sfsdsf
    <Form
      :initial-values="initialValues"
      :form-schema="loginFormSchema"
      :actions="actions"
    >
      <FormFields v-slot="{ resetGeneralError }">
        <ControlledInput
          name="email"
          :label="'email'"
          :placeholder="'inserisci email'"
          @input-click="resetGeneralError"
        />

        <ControlledInput
          type="password"
          name="password"
          :label="'password'"
          :placeholder="'inserisci password'"
          @input-click="resetGeneralError"
        />

        <ControlledCheckbox
          name="rememberMe"
          :label="'ricordami'"
          @input-click="resetGeneralError"
        />
      </FormFields>

      <FormActions v-slot="{ form, isValid }" class="mt-6">
        <Button
          type="submit"
          class="w-full"
          :disabled="!isValid || form?.isSubmitting.value"
          :loading="form?.isSubmitting.value"
        >
          Invia
        </Button>
      </FormActions>
    </Form>
  </div>
</template>
