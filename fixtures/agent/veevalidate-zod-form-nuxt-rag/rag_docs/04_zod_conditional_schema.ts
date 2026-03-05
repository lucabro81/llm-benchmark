/**
 * EXAMPLE: Zod schema with optional fields and conditional validation.
 *
 * Patterns shown:
 * - .optional() marks a field as not required
 * - .superRefine() adds cross-field conditional validation rules
 * - z.infer<typeof schema> derives the TypeScript type
 */

import { z } from "zod";

export const registrationSchema = z.object({
  username: z.string().min(3, "Username: almeno 3 caratteri"),
  email: z.string().email("Email non valida").min(1, "Email obbligatoria"),

  // role drives conditional fields below
  role: z.enum(["user", "admin", "contributor"]),

  // otherInfo is optional by default; made required for "contributor" via superRefine
  otherInfo: z.string().optional(),

  // newsletter enables the frequency field
  newsletter: z.boolean().optional(),

  // frequency is optional; required only when newsletter is true
  frequency: z.enum(["daily", "weekly", "monthly"]).optional(),

  // bio is always optional
  bio: z.string().optional(),
})
.superRefine((data, ctx) => {
  // otherInfo is required when role is "contributor"
  if (data.role === "contributor" && !data.otherInfo) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Descrivi il tuo contributo",
      path: ["otherInfo"],
    });
  }

  // frequency is required when newsletter is true
  if (data.newsletter && !data.frequency) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Seleziona una frequenza",
      path: ["frequency"],
    });
  }
});

export type RegistrationFormValues = z.infer<typeof registrationSchema>;

// Initial values: all optional fields get a safe default (empty string or false/undefined)
export const registrationInitialValues: RegistrationFormValues = {
  username: "",
  email: "",
  role: "user",
  otherInfo: "",
  newsletter: false,
  frequency: undefined,
  bio: "",
};
