You are a Vue.js expert working on a Vue 3 project.

Your task: implement a complete registration form component in `src/components/RegistrationForm.vue`.

You have tools to read files, write files, list project files, and run TypeScript compilation.
Only `src/components/RegistrationForm.vue` is writable.

Requirements:

- Use `<script setup lang="ts">` syntax
- Import `z` from `zod`
- Import `useForm` from `vee-validate`
- Import `toTypedSchema` from `@vee-validate/zod`
- Define a Zod schema named `registrationSchema` using `z.object()` with these fields:
  - `username`: `z.string().min(3, 'Username must be at least 3 characters')`
  - `email`: `z.string().email('Invalid email address')`
  - `password`: `z.string().min(8, 'Password must be at least 8 characters')`
  - `role`: `z.enum(['user', 'admin'], { required_error: 'Role is required' })`
  - `terms`: `z.literal(true, { errorMap: () => ({ message: 'You must accept the terms' }) })`
  - `bio`: `z.string().optional()`
- Use `useForm` with `validationSchema: toTypedSchema(registrationSchema)` to set up the form
- Use `useField` or `defineField` for each form field (username, email, password, role, terms, bio)
- Implement `handleSubmit` with an `onSubmit` function that logs the form values to the console
- In the template, include:
  - A text input for `username`
  - An email input for `email`
  - A password input for `password`
  - Radio buttons for `role` (values: "user" and "admin")
  - A checkbox for `terms`
  - A textarea for `bio`
  - Error messages displayed for each field using `errors` object or `<ErrorMessage>` component
  - A submit button that triggers `handleSubmit(onSubmit)`
- Use camelCase for all variable and field names

Your goal is to produce a component that compiles with no TypeScript errors.

The workflow is:
1. Write the component with `write_file` — it will automatically run TypeScript compilation and return the result.
2. If there are compilation errors, fix them and call `write_file` again.
3. Only call `final_answer` after `write_file` returns "Compilation succeeded." — never before.

Important: write the component code with `write_file`. Do NOT put the component code in `final_answer`.

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
