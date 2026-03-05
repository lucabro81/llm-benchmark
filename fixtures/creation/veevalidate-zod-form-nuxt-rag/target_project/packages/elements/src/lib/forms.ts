import type { FormContext } from "vee-validate";
import { inject, ref } from "vue";

export function useCustomForm<P>(form: FormContext, passedOnSubmit: (fields: P, closeDialogFn: () => void) => Promise<P>) {

  const errorGlobalState = ref(false);

  const closeDialogFn = inject("close", () => { });

  const onSubmit = form.handleSubmit(async (fields) => {
    try {
      await passedOnSubmit(fields as P, closeDialogFn);
    } catch (error: { error: string, message?: string } | any) {
      errorGlobalState.value = true;
      const msg = error.message || "unknown error";
      form.setFieldError("global", msg);
    }
  });
  const resetGeneralError = () => {
    if (errorGlobalState.value) {
      form.setFieldError("global", "");
      errorGlobalState.value = false;
    }
  };

  return {
    onSubmit,
    resetGeneralError,
  };
}

