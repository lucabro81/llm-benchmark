You are a Vue.js expert. Implement a complete registration form component using VeeValidate 4 and Zod for schema validation.

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

Output ONLY the complete Vue component code, no explanations.
