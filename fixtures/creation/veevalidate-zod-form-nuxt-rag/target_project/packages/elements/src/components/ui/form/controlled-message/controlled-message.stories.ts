import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ControlledMessage } from "./index";
import { Form, FormFields } from "@/components/organisms";
import z from "zod";

const meta: Meta<typeof ControlledMessage> = {
  title: "Comperio Design System/Components/Molecules/ControlledMessage",
  component: ControlledMessage,
  tags: ["autodocs"],
};

export default meta;

export const Default: StoryObj<typeof ControlledMessage> = {
  args: {},
  render: (args) => ({
    components: { ControlledMessage, Form, FormFields },
    setup() {
      const formSchema = z.object({
        global: z.string().optional(),
      });

      const initialValues = {
        global: "",
      };

      const onSubmit = async (values: { global?: string }) => {
        console.log("Form submitted with values:", values);
        return values;
      };

      return { args, formSchema, initialValues, onSubmit };
    },
    template: `
      <Form :initial-values="initialValues" :form-schema="formSchema" :actions="{ onSubmit }">
        <FormFields>
          <ControlledMessage />
        </FormFields>
      </Form>
    `,
  }),
  parameters: {
    docs: {
      source: {
        code: `
<script lang="ts" setup>
  const model = ref(null)
  const onClickHandler = (evt) => {
    // manage event
  }
</script>
<template>
<Form ...>
  ...
  <ControlledMessage />
  ...
</Form>
</template>`,
      },
    },
  },
};
