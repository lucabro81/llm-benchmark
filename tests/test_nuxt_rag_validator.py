"""Tests for src/agent/veevalidate_zod_form_nuxt_rag/validator.py.

New pattern checks for the monorepo fixture:
  script_lang, form_component, controlled_components, conditional_rendering,
  zod_schema, required_fields, conditional_fields.

Scoring (0-10):
  +1  script_lang
  +1  form_component
  +2  controlled_components (≥3 of 4 types present)
  +1  conditional_rendering
  +2  zod_schema  (z.object)
  +2  required_fields (all 4 required: username, email, role, bio)
  +1  conditional_fields (≥2 of 3: newsletter, frequency, otherInfo)
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agent.veevalidate_zod_form_nuxt_rag.validator import (
    ASTResult,
    CompilationResult,
    NamingResult,
    validate_ast_structure,
    validate_compilation,
    validate_naming,
)

# ---------------------------------------------------------------------------
# Complete component fixture (all patterns present)
# ---------------------------------------------------------------------------

COMPLETE_COMPONENT = """
<script setup lang="ts">
import {
  Button, ControlledCheckbox, ControlledInput, ControlledRadioGroup, ControlledTextarea,
  Form, FormActions, FormFields,
} from "elements";
import { registrationSchema, type RegistrationFormValues } from "../types";

const initialValues: RegistrationFormValues = {
  username: "", email: "", role: "user",
  otherInfo: "", newsletter: false, frequency: undefined, bio: "",
};

const roleOptions = [
  { value: "user", label: "Utente" },
  { value: "admin", label: "Amministratore" },
  { value: "contributor", label: "Contributore" },
];

const frequencyOptions = [
  { value: "daily", label: "Giornaliero" },
  { value: "weekly", label: "Settimanale" },
  { value: "monthly", label: "Mensile" },
];

const actions = { onSubmit: async (v: RegistrationFormValues) => v };
</script>

<template>
  <Form :initial-values="initialValues" :form-schema="registrationSchema" :actions="actions">
    <FormFields v-slot="{ form, resetGeneralError }">
      <ControlledInput name="username" label="Username" @input-click="resetGeneralError" />
      <ControlledInput name="email" label="Email" type="email" @input-click="resetGeneralError" />
      <ControlledRadioGroup name="role" label="Ruolo" :options="roleOptions" @input-click="resetGeneralError" />
      <ControlledInput v-if="form.values.role === 'contributor'" name="otherInfo" label="Contributo" @input-click="resetGeneralError" />
      <ControlledCheckbox name="newsletter" label="Newsletter" @input-click="resetGeneralError" />
      <ControlledRadioGroup v-if="form.values.newsletter" name="frequency" label="Frequenza" :options="frequencyOptions" @input-click="resetGeneralError" />
      <ControlledTextarea name="bio" label="Bio" placeholder="..." @input-click="resetGeneralError" />
    </FormFields>
    <FormActions v-slot="{ form, isValid }">
      <Button type="submit" :disabled="!isValid || form?.isSubmitting.value">Registrati</Button>
    </FormActions>
  </Form>
</template>
"""

COMPLETE_SCHEMA = """
import { z } from "zod";

export const registrationSchema = z.object({
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

export type RegistrationFormValues = z.infer<typeof registrationSchema>;
"""

# Combined code: what the test_runner feeds to validate_ast_structure
COMPLETE_CODE = COMPLETE_COMPONENT + "\n" + COMPLETE_SCHEMA

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
        result = validate_ast_structure(COMPLETE_CODE, SPEC)
        assert result.score == pytest.approx(10.0)
        assert result.missing == []

    def test_returns_ast_result_instance(self):
        result = validate_ast_structure(COMPLETE_CODE, SPEC)
        assert isinstance(result, ASTResult)

    def test_empty_string_scores_zero(self):
        result = validate_ast_structure("", SPEC)
        assert result.score == pytest.approx(0.0)

    def test_missing_script_lang_ts_reduces_score(self):
        code = COMPLETE_CODE.replace('lang="ts"', 'lang="js"')
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "script_lang" in result.missing

    def test_missing_form_component_reduces_score(self):
        code = COMPLETE_CODE.replace("<Form ", "<FormWrapper ")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "form_component" in result.missing

    def test_missing_controlled_components_reduces_score(self):
        # Remove ControlledTextarea and ControlledCheckbox — only 2 of 4 remain → fails
        code = COMPLETE_CODE.replace("ControlledTextarea", "PlainTextarea").replace("ControlledCheckbox", "PlainCheckbox")
        result = validate_ast_structure(code, SPEC)
        assert "controlled_components" in result.missing
        assert result.score < 10.0

    def test_three_of_four_controlled_components_still_passes(self):
        # Remove only ControlledTextarea — 3 of 4 remain → passes
        code = COMPLETE_CODE.replace("ControlledTextarea", "PlainTextarea")
        result = validate_ast_structure(code, SPEC)
        assert "controlled_components" not in result.missing

    def test_missing_conditional_rendering_reduces_score(self):
        code = COMPLETE_CODE.replace("v-if", "x-removed")
        result = validate_ast_structure(code, SPEC)
        assert result.score == pytest.approx(9.0)
        assert "conditional_rendering" in result.missing

    def test_missing_zod_schema_reduces_score(self):
        code = COMPLETE_CODE.replace("z.object", "z_REMOVED.object")
        result = validate_ast_structure(code, SPEC)
        assert result.score < 10.0
        assert "zod_schema" in result.missing

    def test_missing_required_fields_reduces_score(self):
        code = COMPLETE_CODE.replace("username", "REMOVED").replace("email", "REMOVED2")
        result = validate_ast_structure(code, SPEC)
        assert "required_fields" in result.missing
        assert result.score < 10.0

    def test_all_required_fields_present_gives_points(self):
        result = validate_ast_structure(COMPLETE_CODE, SPEC)
        assert "required_fields" not in result.missing

    def test_missing_conditional_fields_reduces_score(self):
        # Remove all 3 conditional field names
        code = COMPLETE_CODE.replace("newsletter", "REMOVED1").replace("frequency", "REMOVED2").replace("otherInfo", "REMOVED3")
        result = validate_ast_structure(code, SPEC)
        assert "conditional_fields" in result.missing

    def test_two_of_three_conditional_fields_still_passes(self):
        # Remove only 'otherInfo' — 2 of 3 remain → passes
        code = COMPLETE_CODE.replace("otherInfo", "REMOVED")
        result = validate_ast_structure(code, SPEC)
        assert "conditional_fields" not in result.missing

    def test_checks_dict_reflects_results(self):
        result = validate_ast_structure(COMPLETE_CODE, SPEC)
        assert result.checks.get("script_lang") is True
        assert result.checks.get("form_component") is True
        assert result.checks.get("zod_schema") is True

    def test_empty_spec_scores_zero(self):
        result = validate_ast_structure(COMPLETE_CODE, {})
        assert result.score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# validate_compilation
# ---------------------------------------------------------------------------

class TestValidateCompilation:

    def test_success_when_returncode_zero(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = validate_compilation(
                target_project=tmp_path,
                compilation_command="check-types",
                compilation_cwd=tmp_path,
            )
        assert result.success is True
        assert result.errors == []

    def test_failure_when_returncode_nonzero(self, tmp_path):
        stderr = "error TS2307: Cannot find module 'elements'"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr=stderr)
            result = validate_compilation(
                target_project=tmp_path,
                compilation_command="check-types",
                compilation_cwd=tmp_path,
            )
        assert result.success is False
        assert len(result.errors) > 0

    def test_timeout_returns_failure(self, tmp_path):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="npm", timeout=30)):
            result = validate_compilation(
                target_project=tmp_path,
                compilation_command="check-types",
                compilation_cwd=tmp_path,
            )
        assert result.success is False
        assert any("timeout" in e.lower() for e in result.errors)

    def test_returns_compilation_result_instance(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = validate_compilation(
                target_project=tmp_path,
                compilation_command="check-types",
                compilation_cwd=tmp_path,
            )
        assert isinstance(result, CompilationResult)

    def test_raises_on_missing_target_project(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_compilation(
                target_project=tmp_path / "nonexistent",
                compilation_command="check-types",
                compilation_cwd=tmp_path / "nonexistent",
            )


# ---------------------------------------------------------------------------
# validate_naming
# ---------------------------------------------------------------------------

class TestValidateNaming:

    def test_camelcase_variables_score_one(self):
        code = "<script setup lang='ts'>\nconst registrationSchema = {}\nconst initialValues = {}\n</script>"
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == pytest.approx(1.0)
        assert result.follows_conventions is True

    def test_uppercase_variable_scores_zero(self):
        code = "<script setup lang='ts'>\nconst RegistrationSchema = {}\n</script>"
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == pytest.approx(0.0)
        assert result.follows_conventions is False

    def test_empty_conventions_no_violations(self):
        code = "<script setup lang='ts'>\nconst BadName = {}\n</script>"
        result = validate_naming(code, {})
        assert result.score == pytest.approx(1.0)

    def test_returns_naming_result_instance(self):
        result = validate_naming("", {"variables": "camelCase"})
        assert isinstance(result, NamingResult)
