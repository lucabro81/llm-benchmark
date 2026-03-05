import { z } from "zod";

export const loginFormSchema = z.object({
  email: z.string().email("Formato email non valido").min(1, "Email obbligatoria"),
  password: z.string().min(1, "Password obbligatoria"),
  rememberMe: z.boolean().optional(),
});


export type LoginFormValues = z.infer<typeof loginFormSchema>;