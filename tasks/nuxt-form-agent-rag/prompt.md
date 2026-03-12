You are implementing a Vue 3 registration form in a Turborepo monorepo.

## Task

Implement TWO files **in this order**:

1. `apps/web/src/registration/types/index.ts` — Zod schema + TypeScript type
2. `apps/web/src/registration/components/RegistrationForm.vue` — Vue SFC using the `elements` package

Write `types/index.ts` **first** so that RegistrationForm.vue can import from it.
Use `write_file` to write each file, then `run_compilation` to check for TypeScript errors.
`write_file` only writes the file and returns `"File written."` — it does NOT compile.
After each write, call `run_compilation` to get feedback and fix any errors before moving on.

**Use `query_rag` to look up component API examples before writing any code.** The tool has code examples for all available form components and patterns.

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
