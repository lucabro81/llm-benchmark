"""Tests for src/agent/nuxt_form_agent_guided/validator.py.

Same scoring rules as the nuxt-rag fixture:
  +1  script_lang, +1 form_component, +2 controlled_components (≥3/4),
  +1  conditional_rendering, +2 zod_schema, +2 required_fields, +1 conditional_fields (≥2/3)
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.agent.nuxt_form_agent_guided.validator import (
    ASTResult,
    CompilationResult,
    NamingResult,
    validate_ast_structure,
    validate_compilation,
    validate_naming,
)

COMPLETE_CODE = """
<script setup lang="ts">
import {
  Button, ControlledCheckbox, ControlledInput, ControlledRadioGroup, ControlledTextarea,
  Form, FormActions, FormFields,
} from "elements";
import { z } from "zod";

const schema = z.object({
  username: z.string().min(3),
  email: z.string().email(),
  role: z.enum(["user", "admin", "contributor"]),
  otherInfo: z.string().optional(),
  newsletter: z.boolean().optional(),
  frequency: z.enum(["daily", "weekly", "monthly"]).optional(),
  bio: z.string().optional(),
});
const initialValues = { username: "", email: "", role: "user", otherInfo: "", newsletter: false, frequency: undefined, bio: "" };
const roleOptions = [{ value: "user", label: "U" }];
const frequencyOptions = [{ value: "daily", label: "D" }];
const actions = { onSubmit: async (v: any) => v };
</script>
<template>
  <Form :initial-values="initialValues" :form-schema="schema" :actions="actions">
    <FormFields v-slot="{ form, resetGeneralError }">
      <ControlledInput name="username" @input-click="resetGeneralError" />
      <ControlledInput name="email" type="email" @input-click="resetGeneralError" />
      <ControlledRadioGroup name="role" :options="roleOptions" @input-click="resetGeneralError" />
      <ControlledInput v-if="form.values.role === 'contributor'" name="otherInfo" @input-click="resetGeneralError" />
      <ControlledCheckbox name="newsletter" @input-click="resetGeneralError" />
      <ControlledRadioGroup v-if="form.values.newsletter" name="frequency" :options="frequencyOptions" @input-click="resetGeneralError" />
      <ControlledTextarea name="bio" @input-click="resetGeneralError" />
    </FormFields>
    <FormActions v-slot="{ form, isValid }">
      <Button type="submit" :disabled="!isValid">OK</Button>
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
        assert validate_ast_structure(COMPLETE_CODE, SPEC).score == pytest.approx(10.0)

    def test_returns_ast_result(self):
        assert isinstance(validate_ast_structure(COMPLETE_CODE, SPEC), ASTResult)

    def test_empty_string_scores_zero(self):
        assert validate_ast_structure("", SPEC).score == pytest.approx(0.0)

    def test_missing_script_lang_reduces_score(self):
        code = COMPLETE_CODE.replace('lang="ts"', 'lang="js"')
        result = validate_ast_structure(code, SPEC)
        assert "script_lang" in result.missing

    def test_missing_form_component_reduces_score(self):
        result = validate_ast_structure(COMPLETE_CODE.replace("<Form ", "<FormWrapper "), SPEC)
        assert "form_component" in result.missing

    def test_three_of_four_controlled_passes(self):
        code = COMPLETE_CODE.replace("ControlledTextarea", "PlainTextarea")
        assert "controlled_components" not in validate_ast_structure(code, SPEC).missing

    def test_two_of_four_controlled_fails(self):
        code = COMPLETE_CODE.replace("ControlledTextarea", "PT").replace("ControlledCheckbox", "PC")
        assert "controlled_components" in validate_ast_structure(code, SPEC).missing

    def test_missing_v_if_reduces_score(self):
        assert "conditional_rendering" in validate_ast_structure(
            COMPLETE_CODE.replace("v-if", "x-rm"), SPEC
        ).missing

    def test_missing_zod_reduces_score(self):
        assert "zod_schema" in validate_ast_structure(
            COMPLETE_CODE.replace("z.object", "z_RM.object"), SPEC
        ).missing

    def test_all_required_fields_pass(self):
        assert "required_fields" not in validate_ast_structure(COMPLETE_CODE, SPEC).missing

    def test_two_of_three_conditional_passes(self):
        code = COMPLETE_CODE.replace("otherInfo", "REMOVED")
        assert "conditional_fields" not in validate_ast_structure(code, SPEC).missing


class TestValidateCompilation:

    def test_success_on_zero_returncode(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert validate_compilation(tmp_path, "check-types", tmp_path).success is True

    def test_failure_on_nonzero_returncode(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stdout="", stderr="error TS2307: missing")
            assert validate_compilation(tmp_path, "check-types", tmp_path).success is False

    def test_raises_on_missing_project(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_compilation(tmp_path / "nx", "check-types", tmp_path / "nx")

    def test_returns_compilation_result(self, tmp_path):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert isinstance(validate_compilation(tmp_path, "check-types", tmp_path), CompilationResult)


class TestValidateNaming:

    def test_camelcase_scores_one(self):
        assert validate_naming("const myVar = {}", {"variables": "camelCase"}).score == pytest.approx(1.0)

    def test_uppercase_scores_zero(self):
        assert validate_naming("const MyVar = {}", {"variables": "camelCase"}).score == pytest.approx(0.0)

    def test_empty_conventions_no_violations(self):
        assert validate_naming("const BadName = {}", {}).score == pytest.approx(1.0)

    def test_returns_naming_result(self):
        assert isinstance(validate_naming("", {"variables": "camelCase"}), NamingResult)
