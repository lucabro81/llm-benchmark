<!--
  EXAMPLE: ControlledRadioGroup — radio buttons driven by an options array.

  Pattern:
  - ControlledRadioGroup takes name, label, :options (array of { value, label })
  - orientation is "vertical" (default) or "horizontal"
  - A second ControlledRadioGroup can be shown conditionally based on form.values
-->
<script setup lang="ts">
import { Button, ControlledRadioGroup, Form, FormActions, FormFields } from "elements";
import { z } from "zod";

const schema = z.object({
  role: z.enum(["user", "admin", "contributor"]),
  // notificationChannel is only relevant when role is "admin"
  notificationChannel: z.enum(["email", "slack"]).optional(),
});

type FormValues = z.infer<typeof schema>;

const initialValues: FormValues = {
  role: "user",
  notificationChannel: undefined,
};

const roleOptions = [
  { value: "user", label: "Utente" },
  { value: "admin", label: "Amministratore" },
  { value: "contributor", label: "Contributore" },
];

const channelOptions = [
  { value: "email", label: "Email" },
  { value: "slack", label: "Slack" },
];

const actions = {
  onSubmit: async (values: FormValues) => values,
};
</script>

<template>
  <Form :initial-values="initialValues" :form-schema="schema" :actions="actions">

    <FormFields v-slot="{ form, resetGeneralError }">
      <!--
        :options is an array of { value: string, label: string }.
        The selected value is stored in form.values.role.
      -->
      <ControlledRadioGroup
        name="role"
        label="Ruolo"
        :options="roleOptions"
        @input-click="resetGeneralError"
      />

      <!-- Show a second radio group only when role === "admin" -->
      <ControlledRadioGroup
        v-if="form.values.role === 'admin'"
        name="notificationChannel"
        label="Canale notifiche"
        :options="channelOptions"
        orientation="horizontal"
        @input-click="resetGeneralError"
      />
    </FormFields>

    <FormActions v-slot="{ form, isValid }">
      <Button type="submit" :disabled="!isValid || form?.isSubmitting.value">
        Conferma
      </Button>
    </FormActions>

  </Form>
</template>
