import { type ClassValue, clsx } from 'clsx'
import { ref, watch, type Ref } from "vue";
import { twMerge } from 'tailwind-merge'
import type { FormContext } from 'vee-validate';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

function watchFormValues(form: FormContext, isValid: Ref<boolean>) {
  watch(
    () => form,
    (newForm) => {
      isValid.value = newForm.meta.value.valid;
    },
    { deep: true }
  );
}
export function useIsFormValid(form: FormContext) {
  const isValid = ref(false);
  watchFormValues(form, isValid);
  return isValid;
}

export function valueUpdater<T>(updaterOrValue: T, ref: Ref) {
  ref.value = typeof updaterOrValue === 'function'
    ? updaterOrValue(ref.value)
    : updaterOrValue
}

export function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}