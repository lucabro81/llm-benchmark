You are a Vue.js expert. Refactor the following component to add complete TypeScript type safety.

Requirements:
- Add `lang="ts"` to script tag
- Import the `User` type from `'@/types/user'` using `import type` syntax
- Import `ComputedRef` from 'vue' (alongside the existing `computed` import)
- Define interface `UserProfileProps` for component props:
  - `user`: User
  - `editable`: boolean
- Define interface `UserProfileEmits` for component emits with typed payloads:
  - `'update:user'`: [user: User]
  - `'delete'`: [id: number]
- Use `defineProps<UserProfileProps>()` syntax
- Use `defineEmits<UserProfileEmits>()` syntax
- Annotate `displayName` with return type `ComputedRef<string>`
- Maintain exact same functionality and keep template unchanged

Original code:
```vue
{{original_code}}
```

Output ONLY the complete refactored component code, no explanations.
