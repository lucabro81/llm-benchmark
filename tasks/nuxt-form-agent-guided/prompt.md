You are implementing a Vue 3 registration form in a Turborepo monorepo.

## Task

Implement `RegistrationForm.vue` at:
`apps/web/src/registration/components/RegistrationForm.vue`

### Required fields

| Field       | Component             | Constraints                                                                 |
|-------------|----------------------|-----------------------------------------------------------------------------|
| `username`  | ControlledInput       | required, min 3 chars                                                       |
| `email`     | ControlledInput       | type="email", required, valid email                                         |
| `role`      | ControlledRadioGroup  | options: "user", "admin", "contributor"                                    |
| `otherInfo` | ControlledInput       | visible only when `role === "contributor"`                                  |
| `newsletter`| ControlledCheckbox    |                                                                             |
| `frequency` | ControlledRadioGroup  | options: "daily", "weekly", "monthly"; visible only when `newsletter` true  |
| `bio`       | ControlledTextarea    | optional                                                                    |

### Conditional validation

Use Zod `.superRefine()` for cross-field rules:
- `otherInfo` required when `role === "contributor"`
- `frequency` required when `newsletter === true`

## How to use your tools

Use `write_file` to write the component, then `run_compilation` to check for TypeScript errors:
- Path: `apps/web/src/registration/components/RegistrationForm.vue`
- `write_file` only writes the file and returns `"File written."` — it does NOT compile
- After writing, always call `run_compilation` to get TypeScript feedback
- Fix any errors reported and repeat until compilation succeeds

Write a **single Vue SFC** file:
- Use `<script setup lang="ts">`
- Define the Zod schema and TypeScript types **inline** in the script block (no imports from local files)

---

## Component API Reference

Use ONLY the components from the `elements` package shown below.

### 01_basic_form.vue

```vue
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

```

### 02_checkbox_reveals_field.vue

```vue
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

```

### 03_radio_group.vue

```vue
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

```

### 04_zod_conditional_schema.ts

```ts
/**
 * EXAMPLE: Zod schema with optional fields and conditional validation.
 *
 * Patterns shown:
 * - .optional() marks a field as not required
 * - .superRefine() adds cross-field conditional validation rules
 * - z.infer<typeof schema> derives the TypeScript type
 */

import { z } from "zod";

export const registrationSchema = z.object({
  username: z.string().min(3, "Username: almeno 3 caratteri"),
  email: z.string().email("Email non valida").min(1, "Email obbligatoria"),

  // role drives conditional fields below
  role: z.enum(["user", "admin", "contributor"]),

  // otherInfo is optional by default; made required for "contributor" via superRefine
  otherInfo: z.string().optional(),

  // newsletter enables the frequency field
  newsletter: z.boolean().optional(),

  // frequency is optional; required only when newsletter is true
  frequency: z.enum(["daily", "weekly", "monthly"]).optional(),

  // bio is always optional
  bio: z.string().optional(),
})
.superRefine((data, ctx) => {
  // otherInfo is required when role is "contributor"
  if (data.role === "contributor" && !data.otherInfo) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Descrivi il tuo contributo",
      path: ["otherInfo"],
    });
  }

  // frequency is required when newsletter is true
  if (data.newsletter && !data.frequency) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Seleziona una frequenza",
      path: ["frequency"],
    });
  }
});

export type RegistrationFormValues = z.infer<typeof registrationSchema>;

// Initial values: all optional fields get a safe default (empty string or false/undefined)
export const registrationInitialValues: RegistrationFormValues = {
  username: "",
  email: "",
  role: "user",
  otherInfo: "",
  newsletter: false,
  frequency: undefined,
  bio: "",
};

```

### 05_textarea_and_full_form.vue

```vue
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

```

Rules for valid JSON strings:
- Newlines inside strings MUST be written as `\n` (backslash + n), NOT as actual line breaks
- Double quotes inside strings MUST be escaped as `\"`
- Backtick characters do NOT need escaping

WRONG — text before the JSON block will be rejected:
```
Here is my implementation... I will now write the component.
```json
{ "name": "write_file", ... }
```
```

CORRECT — the JSON code block is the entire response, nothing else.