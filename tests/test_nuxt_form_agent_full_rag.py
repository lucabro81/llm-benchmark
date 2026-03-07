"""Tests for src/agent/nuxt_form_agent_full/rag.py — QueryRagTool."""

from pathlib import Path

import pytest

from src.agent.nuxt_form_agent_full.rag import QueryRagTool


def _make_rag_docs(tmp_path: Path) -> Path:
    """Create a rag_docs directory with two clearly-distinguishable example files."""
    docs = tmp_path / "rag_docs"
    docs.mkdir()

    # Document 1: exclusively about Form/FormFields/FormActions composition.
    # Distinctive tokens: formfields, formactions, initialvalues, actions, submission
    (docs / "01_basic_form.vue").write_text(
        "<!-- EXAMPLE: basic form using Form FormFields FormActions pattern -->\n"
        "<Form :initial-values='initialValues' :form-schema='schema' :actions='actions'>\n"
        "  <FormFields v-slot='{ resetGeneralError }'>\n"
        "    <ControlledInput name='email' label='Email' @input-click='resetGeneralError' />\n"
        "  </FormFields>\n"
        "  <FormActions v-slot='{ form, isValid }'>\n"
        "    <Button type='submit' :disabled='!isValid || form.isSubmitting.value'>Submit</Button>\n"
        "  </FormActions>\n"
        "</Form>\n"
        "<!-- actions initialValues FormFields FormActions submission -->"
    )

    # Document 2: exclusively about checkbox/conditional/newsletter/frequency.
    # Distinctive tokens: checkbox, newsletter, conditional, frequency, reveals, toggle
    (docs / "02_checkbox_reveals_field.vue").write_text(
        "<!-- EXAMPLE: checkbox reveals conditional field newsletter frequency toggle -->\n"
        "<ControlledCheckbox name='newsletter' label='Newsletter subscription' />\n"
        "<ControlledRadioGroup\n"
        "  v-if='form.values.newsletter'\n"
        "  name='frequency'\n"
        "  label='Notification frequency'\n"
        "  :options='frequencyOptions'\n"
        "/>\n"
        "<!-- conditional toggle newsletter frequency checkbox reveals -->"
    )
    return docs


class TestQueryRagToolInit:

    def test_loads_documents_from_directory(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        assert len(tool.documents) == 2

    def test_raises_on_missing_directory(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            QueryRagTool(rag_docs_path=tmp_path / "nonexistent")

    def test_document_names_include_filenames(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        names = [d["name"] for d in tool.documents]
        assert any("01_basic_form" in n for n in names)
        assert any("02_checkbox_reveals_field" in n for n in names)


class TestQueryRagToolForward:

    def test_returns_string(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        result = tool.forward("basic form")
        assert isinstance(result, str)

    def test_relevant_doc_returned_for_basic_form_query(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        result = tool.forward("basic form Form FormFields FormActions")
        assert "01_basic_form" in result or "Form" in result

    def test_relevant_doc_returned_for_conditional_query(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        result = tool.forward("checkbox reveals conditional field v-if")
        assert "02_checkbox_reveals_field" in result or "newsletter" in result

    def test_empty_query_returns_something(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        result = tool.forward("")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_contains_file_content(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        result = tool.forward("ControlledInput schema")
        # Result must contain actual file content, not just a filename
        assert "ControlledInput" in result or "schema" in result

    def test_tool_name_and_description_set(self, tmp_path):
        docs = _make_rag_docs(tmp_path)
        tool = QueryRagTool(rag_docs_path=docs)
        assert tool.name == "query_rag"
        assert len(tool.description) > 10
