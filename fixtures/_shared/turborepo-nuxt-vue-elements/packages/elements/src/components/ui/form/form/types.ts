/**
 * Actions Form Interface
 *
 * Defines the structure for form actions passed to the Form component.
 * The ActionsForm interface requires a mandatory `onSubmit` function, but can contain
 * any other custom action that can be used in the FormActions component.
 *
 * @template P - The type of the form values (same as initialValues)
 *
 * Example:
 * ```typescript
 * const actions: ActionsForm<{ email: string; password: string }> = {
 *   onSubmit: async (values) => {
 *     // Submit logic
 *     return values;
 *   },
 *   forgotPassword: () => {
 *     // Custom action
 *   },
 * };
 * ```
 */
export interface ActionsForm<P> {
  /**
   * Required submit handler called when the form is submitted.
   * @param values - The validated form values
   * @param closeDialogFn - Optional function to close a dialog after submission
   * @returns Promise resolving to the submitted values
   */
  onSubmit: (values: P, closeDialogFn?: () => void) => Promise<P>;
  /** Any other custom actions that can be used in FormActions component */
  [key: string]: unknown;
}