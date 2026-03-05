import type { HTMLAttributes } from "vue";

export interface ControlledInputProps<T = string> {
  name: string;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  description?: string;
  defaultValue?: T;
  modelValue?: T;
  addOnText?: string;
  type?: 'text' | 'password' | 'email' | 'number' | 'tel' | 'url' | 'date' | 'file';
  class?: HTMLAttributes["class"];
}