<!--
  EXAMPLE: Form with all four controlled component types together.

  Components available from "elements":
  - ControlledInput     — text, email, password, number, tel, url, date
  - ControlledCheckbox  — single boolean toggle
  - ControlledRadioGroup — exclusive choice from an options array
  - ControlledTextarea  — multiline text

  This example shows them all in one form.
-->
<script setup lang="ts">
import {
  Button,
  ControlledCheckbox,
  ControlledInput,
  ControlledRadioGroup,
  ControlledTextarea,
  Form,
  FormActions,
  FormFields,
} from "elements";
import { z } from "zod";

const profileSchema = z.object({
  username: z.string().min(3, "Almeno 3 caratteri"),
  email: z.string().email("Email non valida"),
  role: z.enum(["user", "admin"]),
  newsletter: z.boolean().optional(),
  bio: z.string().optional(),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

const initialValues: ProfileFormValues = {
  username: "",
  email: "",
  role: "user",
  newsletter: false,
  bio: "",
};

const roleOptions = [
  { value: "user", label: "Utente" },
  { value: "admin", label: "Amministratore" },
];

const actions = {
  onSubmit: async (values: ProfileFormValues) => {
    console.log("submitted:", values);
    return values;
  },
};
</script>

<template>
  <div class="w-full max-w-md">
    <Form :initial-values="initialValues" :form-schema="profileSchema" :actions="actions">

      <FormFields v-slot="{ resetGeneralError }">
        <!-- text input -->
        <ControlledInput
          name="username"
          label="Username"
          placeholder="il tuo username"
          @input-click="resetGeneralError"
        />

        <!-- email input -->
        <ControlledInput
          name="email"
          label="Email"
          type="email"
          placeholder="nome@esempio.com"
          @input-click="resetGeneralError"
        />

        <!-- radio group: options drive the available choices -->
        <ControlledRadioGroup
          name="role"
          label="Ruolo"
          :options="roleOptions"
          @input-click="resetGeneralError"
        />

        <!-- checkbox -->
        <ControlledCheckbox
          name="newsletter"
          label="Iscrivimi alla newsletter"
          @input-click="resetGeneralError"
        />

        <!-- textarea: multiline free text -->
        <ControlledTextarea
          name="bio"
          label="Biografia"
          placeholder="Raccontaci qualcosa di te..."
          @input-click="resetGeneralError"
        />
      </FormFields>

      <FormActions v-slot="{ form, isValid }" class="mt-6">
        <Button
          type="submit"
          class="w-full"
          :disabled="!isValid || form?.isSubmitting.value"
        >
          Salva profilo
        </Button>
      </FormActions>

    </Form>
  </div>
</template>
