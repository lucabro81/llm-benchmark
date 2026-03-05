"""Tests for src/creation/nuxt_form_creation/validator.py.

Same scoring rules as the nuxt-rag fixture:
  +1  script_lang
  +1  form_component
  +2  controlled_components (≥3 of 4)
  +1  conditional_rendering
  +2  zod_schema
  +2  required_fields (all 4)
  +1  conditional_fields (≥2 of 3)
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.creation.nuxt_form_creation.validator import (
    ASTResult,
    CompilationResult,
    NamingResult,
    validate_ast_structure,
    validate_compilation,
    validate_naming,
)

COMPLETE_COMPONENT = """
<script setup lang="ts">
import {
  Button, ControlledCheckbox, ControlledInput, ControlledRadioGroup, ControlledTextarea,
  Form, FormActions, FormFields,
} from "elements";
import { z } from "zod";

const registrationSchema = z.object({
  username: z.string().min(3),
  email: z.string().email(),
  role: z.enum(["user", "admin", "contributor"]),
  otherInfo: z.string().optional(),
  newsletter: z.boolean().optional(),
  frequency: z.enum(["daily", "weekly", "monthly"]).optional(),
  bio: z.string().optional(),
}).superRefine((data, ctx) => {
  if (data.role === "contributor" && !data.otherInfo) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "required", path: ["otherInfo"] });
  }
  if (data.newsletter && !data.frequency) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "required", path: ["frequency"] });
  }
});

type RegistrationFormValues = z.infer<typeof registrationSchema>;

const initialValues: RegistrationFormValues = {
  username: "", email: "", role: "user",
  otherInfo: "", newsletter: false, frequency: undefined, bio: "",
};

const roleOptions = [{ value: "user", label: "Utente" }, { value: "contributor", label: "Contributore" }];
const frequencyOptions = [{ value: "daily", label: "Daily" }];
const actions = { onSubmit: async (v: RegistrationFormValues) => v };
</script>

<template>
  <Form :initial-values="initialValues" :form-schema="registrationSchema" :actions="actions">
    <FormFields v-slot="{ form, resetGeneralError }">
      <ControlledInput name="username" label="Username" @input-click="resetGeneralError" />
      <ControlledInput name="email" label="Email" type="email" @input-click="resetGeneralError" />
      <ControlledRadioGroup name="role" label="Ruolo" :options="roleOptions" @input-click="resetGeneralError" />
      <ControlledInput v-if="form.values.role === 'contributor'" name="otherInfo" label="Info" @input-click="resetGeneralError" />
      <ControlledCheckbox name="newsletter" label="Newsletter" @input-click="resetGeneralError" />
      <ControlledRadioGroup v-if="form.values.newsletter" name="frequency" label="Frequenza" :options="frequencyOptions" @input-click="resetGeneralError" />
      <ControlledTextarea name="bio" label="Bio" @input-click="resetGeneralError" />
    </FormFields>
    <FormActions v-slot="{ form, isValid }">
      <Button type="submit" :disabled="!isValid">Registrati</Button>
    </FormActions>
  </Form>
</template>
"""

SPEC = {
    "script_lang": "ts",
    "form_component": "<Form",
    "controlled_components": ["ControlledInput", "ControlledRadioGroup", "ControlledCheckbox", "ControlledTextarea"],
    "conditional_rendering": "v-if",
    "zod_schema": "z.object",
    "required_fields": ["username", "email", "role", "bio"],
    "conditional_fields": ["newsletter", "frequency", "otherInfo"],
}


class TestValidateAstStructure:

    def test_complete_code_scores_ten(self):
        result = validate_ast_structure(COMPLETE_COMPONENT, SPEC)
        assert result.score == pytest.approx(10.0)
        assert result.missing == []

    def test_returns_ast_result_instance(self):
        assert isinstance(validate_ast_structure(COMPLETE_COMPONENT, SPEC), ASTResult)

    def test_empty_string_scores_zero(self):
        assert validate_ast_structure("", SPEC).score == pytest.approx(0.0)

    def test_missing_script_lang_ts_reduces_score(self):
        code = COMPLETE_COMPONENT.replace('lang="ts"', 'lang="js"')
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "script_lang" in result.missing

    def test_missing_form_component_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("<Form ", "<FormWrapper ")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "form_component" in result.missing

    def test_two_of_four_controlled_components_fails(self):
        code = COMPLETE_COMPONENT.replace("ControlledTextarea", "PlainTextarea").replace("ControlledCheckbox", "PlainCheckbox")
        result = validate_ast_structure(code, SPEC)
        assert "controlled_components" in result.missing

    def test_three_of_four_controlled_components_passes(self):
        code = COMPLETE_COMPONENT.replace("ControlledTextarea", "PlainTextarea")
        result = validate_ast_structure(code, SPEC)
        assert "controlled_components" not in result.missing

    def test_missing_v_if_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("v-if", "x-removed")
        result = validate_ast_structure(code, SPEC)
        assert "conditional_rendering" in result.missing

    def test_missing_zod_schema_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("z.object", "z_REMOVED.object")
        result = validate_ast_structure(code, SPEC)
        assert "zod_schema" in result.missing

    def test_all_required_fields_present(self):
        result = validate_ast_structure(COMPLETE_COMPONENT, SPEC)
        assert "required_fields" not in result.missing

    def test_missing_required_fields_reduces_score(self):
        code = COMPLETE_COMPONENT.replace("username", "REMOVED")
        result = validate_ast_structure(code, SPEC)
        assert "required_fields" in result.missing

    def test_two_of_three_conditional_fields_passes(self):
        code = COMPLETE_COMPONENT.replace("otherInfo", "REMOVED")
        result = validate_ast_structure(code, SPEC)
        assert "conditional_fields" not in result.missing

    def test_all_conditional_fields_missing_fails(self):
        code = COMPLETE_COMPONENT.replace("newsletter", "R1").replace("frequency", "R2").replace("otherInfo", "R3")
        result = validate_ast_structure(code, SPEC)
        assert "conditional_fields" in result.missing

    def test_checks_dict_populated(self):
        result = validate_ast_structure(COMPLETE_COMPONENT, SPEC)
        assert result.checks.get("script_lang") is True
        assert result.checks.get("form_component") is True
        assert result.checks.get("zod_schema") is True


class TestValidateCompilation:

    def test_success_on_returncode_zero(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = validate_compilation(tmp_path, "check-types", tmp_path)
        assert result.success is True

    def test_failure_on_nonzero_returncode(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stdout="", stderr="error TS2307: not found")
            result = validate_compilation(tmp_path, "check-types", tmp_path)
        assert result.success is False
        assert len(result.errors) > 0

    def test_timeout_returns_failure(self, tmp_path):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="npm", timeout=60)):
            result = validate_compilation(tmp_path, "check-types", tmp_path)
        assert result.success is False

    def test_returns_compilation_result(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert isinstance(validate_compilation(tmp_path, "check-types", tmp_path), CompilationResult)

    def test_raises_on_missing_target_project(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_compilation(tmp_path / "nonexistent", "check-types", tmp_path / "nonexistent")


class TestValidateNaming:

    def test_camelcase_scores_one(self):
        code = "const registrationSchema = {}\nconst initialValues = {}"
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == pytest.approx(1.0)
        assert result.follows_conventions is True

    def test_uppercase_variable_scores_zero(self):
        result = validate_naming("const BadName = {}", {"variables": "camelCase"})
        assert result.score == pytest.approx(0.0)

    def test_empty_conventions_no_violations(self):
        result = validate_naming("const BadName = {}", {})
        assert result.score == pytest.approx(1.0)

    def test_returns_naming_result(self):
        assert isinstance(validate_naming("", {"variables": "camelCase"}), NamingResult)
