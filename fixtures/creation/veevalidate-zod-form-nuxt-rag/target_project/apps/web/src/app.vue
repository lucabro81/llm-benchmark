<script setup lang="ts">
import { LoginForm } from "./login/components";
import type { LoginFormValues } from "./login/types";

const onSubmit = async (values: LoginFormValues): Promise<LoginFormValues> => {
  await new Promise(resolve => setTimeout(resolve, 2000));
  return values;
};
</script>

<template>
  <LoginForm :on-submit="onSubmit" />
</template>
