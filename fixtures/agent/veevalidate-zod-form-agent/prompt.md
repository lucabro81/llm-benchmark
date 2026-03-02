You are a Vue.js expert working on a Vue 3 project.

Your task: implement a complete registration form component in `src/components/RegistrationForm.vue`.

You have tools to read files, write files, list project files, and run TypeScript compilation.
Only `src/components/RegistrationForm.vue` is writable.

---

## Reference Example

Below is a minimal working login form using VeeValidate + Zod. Use it as your guide for the pattern — imports, schema setup, field binding, and error display all follow the same structure regardless of field count or type.

```vue
<script setup lang="ts">
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'

const loginSchema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Too short'),
})

const { defineField, handleSubmit, errors } = useForm({
  validationSchema: toTypedSchema(loginSchema),
})

const [email, emailAttrs] = defineField('email')
const [password, passwordAttrs] = defineField('password')

const onSubmit = handleSubmit((values) => {
  console.log(values)
})
</script>

<template>
  <form @submit.prevent="onSubmit">
    <div>
      <input v-model="email" v-bind="emailAttrs" type="email" />
      <span>{{ errors.email }}</span>
    </div>
    <div>
      <input v-model="password" v-bind="passwordAttrs" type="password" />
      <span>{{ errors.password }}</span>
    </div>
    <button type="submit">Login</button>
  </form>
</template>
```

Key points:
- `defineField('fieldName')` returns `[modelValue, inputAttrs]` — always bind both with `v-model` and `v-bind`
- `errors.fieldName` holds the validation message for each field
- `handleSubmit(fn)` wraps your submit handler and runs validation before calling `fn`

---

## Requirements for your component

Implement `src/components/RegistrationForm.vue` with the following:

**Zod schema** named `registrationSchema`:
- `username`: `z.string().min(3, 'Username must be at least 3 characters')`
- `email`: `z.string().email('Invalid email address')`
- `password`: `z.string().min(8, 'Password must be at least 8 characters')`
- `role`: `z.enum(['user', 'admin'], { required_error: 'Role is required' })`
- `terms`: `z.literal(true, { errorMap: () => ({ message: 'You must accept the terms' }) })`
- `bio`: `z.string().optional()`

**Form setup**: `useForm({ validationSchema: toTypedSchema(registrationSchema) })`

**Fields** (via `defineField`): username, email, password, role, terms, bio

**Template**:
- Text input for `username`
- Email input for `email`
- Password input for `password`
- Radio buttons for `role` (values: `"user"` and `"admin"`)
- Checkbox for `terms`
- Textarea for `bio`
- Error message for each field (use `errors.fieldName`)
- Submit button that calls `handleSubmit(onSubmit)`

**`onSubmit`**: logs form values to the console.

Your goal is to produce a component that compiles with no TypeScript errors.

---

## Workflow

1. Write the component with `write_file` — it will automatically run TypeScript compilation and return the result.
2. If there are compilation errors, fix them and call `write_file` again.
3. Only call `final_answer` after `write_file` returns "Compilation succeeded." — never before.

Important: write the component code with `write_file`. Do NOT put the component code in `final_answer`.

---

## Tool Call Format

When calling a tool, output ONLY a valid JSON code block — no explanation, no reasoning text before or after it:

```json
{
  "name": "write_file",
  "arguments": {
    "path": "src/components/RegistrationForm.vue",
    "content": "line1\nline2\nline3"
  }
}
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
