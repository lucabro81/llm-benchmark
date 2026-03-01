"""Tests for src/agent/common/tools.py - tool factory functions.

TDD Red phase: all tests fail until tools.py is implemented.

Requires smolagents to be installed (pip install smolagents).
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agent.common.tools import make_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_tool(tools, name):
    """Return the tool with the given name from the tools list."""
    return next((t for t in tools if t.name == name), None)


# ---------------------------------------------------------------------------
# make_tools factory
# ---------------------------------------------------------------------------

class TestMakeTools:
    def test_returns_four_tools(self, tmp_path):
        tools = make_tools(tmp_path, [])
        assert len(tools) == 4

    def test_tools_are_callable(self, tmp_path):
        tools = make_tools(tmp_path, [])
        for t in tools:
            assert callable(t)

    def test_tool_names_are_correct(self, tmp_path):
        tools = make_tools(tmp_path, [])
        names = {t.name for t in tools}
        assert names == {"read_file", "write_file", "list_files", "run_compilation"}

    def test_separate_calls_produce_independent_tools(self, tmp_path):
        """Each call to make_tools should produce independent closures."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "test.txt").write_text("from a")
        (dir_b / "test.txt").write_text("from b")

        tools_a = make_tools(dir_a, [])
        tools_b = make_tools(dir_b, [])

        read_a = _get_tool(tools_a, "read_file")
        read_b = _get_tool(tools_b, "read_file")

        assert read_a("test.txt") == "from a"
        assert read_b("test.txt") == "from b"


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

class TestReadFileTool:
    def test_reads_existing_file(self, tmp_path):
        (tmp_path / "hello.vue").write_text("<template>hello</template>")
        tools = make_tools(tmp_path, [])
        read_file = _get_tool(tools, "read_file")

        assert read_file("hello.vue") == "<template>hello</template>"

    def test_reads_file_in_subdirectory(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.vue").write_text("app content")
        tools = make_tools(tmp_path, [])
        read_file = _get_tool(tools, "read_file")

        assert read_file("src/App.vue") == "app content"

    def test_returns_error_for_missing_file(self, tmp_path):
        tools = make_tools(tmp_path, [])
        read_file = _get_tool(tools, "read_file")

        result = read_file("nonexistent.vue")
        assert result.startswith("ERROR:")

    def test_returns_error_for_path_traversal(self, tmp_path):
        tools = make_tools(tmp_path, [])
        read_file = _get_tool(tools, "read_file")

        result = read_file("../../../etc/passwd")
        assert result.startswith("ERROR:")

    def test_returns_error_for_absolute_path_outside_project(self, tmp_path):
        tools = make_tools(tmp_path, [])
        read_file = _get_tool(tools, "read_file")

        result = read_file("/etc/passwd")
        assert result.startswith("ERROR:")


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

class TestWriteFileTool:
    def test_writes_allowed_file(self, tmp_path):
        (tmp_path / "src").mkdir()
        tools = make_tools(tmp_path, ["src/Comp.vue"])
        write_file = _get_tool(tools, "write_file")

        result = write_file("src/Comp.vue", "new content")
        assert result == "OK"
        assert (tmp_path / "src" / "Comp.vue").read_text() == "new content"

    def test_rejects_disallowed_path(self, tmp_path):
        tools = make_tools(tmp_path, ["src/Allowed.vue"])
        write_file = _get_tool(tools, "write_file")

        result = write_file("src/Other.vue", "content")
        assert result.startswith("ERROR:")
        assert not (tmp_path / "src" / "Other.vue").exists()

    def test_rejects_path_traversal(self, tmp_path):
        tools = make_tools(tmp_path, ["../evil.txt"])
        write_file = _get_tool(tools, "write_file")

        result = write_file("../evil.txt", "evil")
        assert result.startswith("ERROR:")

    def test_creates_parent_dirs_if_needed(self, tmp_path):
        tools = make_tools(tmp_path, ["src/components/New.vue"])
        write_file = _get_tool(tools, "write_file")

        result = write_file("src/components/New.vue", "content")
        assert result == "OK"
        assert (tmp_path / "src" / "components" / "New.vue").exists()

    def test_overwrites_existing_file(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "Comp.vue").write_text("old")
        tools = make_tools(tmp_path, ["src/Comp.vue"])
        write_file = _get_tool(tools, "write_file")

        write_file("src/Comp.vue", "new")
        assert (tmp_path / "src" / "Comp.vue").read_text() == "new"


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------

class TestListFilesTool:
    def test_lists_files_in_root(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.vue").write_text("")
        (tmp_path / "README.md").write_text("")
        tools = make_tools(tmp_path, [])
        list_files = _get_tool(tools, "list_files")

        result = list_files(".")
        assert "README.md" in result
        assert "src/App.vue" in result

    def test_lists_files_in_subdirectory(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "Comp.vue").write_text("")
        tools = make_tools(tmp_path, [])
        list_files = _get_tool(tools, "list_files")

        result = list_files("src")
        assert "Comp.vue" in result

    def test_excludes_node_modules(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.vue").write_text("")
        tools = make_tools(tmp_path, [])
        list_files = _get_tool(tools, "list_files")

        result = list_files(".")
        assert "node_modules" not in result
        assert "src/App.vue" in result

    def test_excludes_git(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.vue").write_text("")
        tools = make_tools(tmp_path, [])
        list_files = _get_tool(tools, "list_files")

        result = list_files(".")
        assert ".git" not in result
        assert "src/App.vue" in result

    def test_returns_error_for_nonexistent_directory(self, tmp_path):
        tools = make_tools(tmp_path, [])
        list_files = _get_tool(tools, "list_files")

        result = list_files("nonexistent")
        assert result.startswith("ERROR:")

    def test_returns_error_for_path_traversal(self, tmp_path):
        tools = make_tools(tmp_path, [])
        list_files = _get_tool(tools, "list_files")

        result = list_files("../../")
        assert result.startswith("ERROR:")

    def test_returns_empty_marker_for_empty_directory(self, tmp_path):
        (tmp_path / "empty").mkdir()
        tools = make_tools(tmp_path, [])
        list_files = _get_tool(tools, "list_files")

        result = list_files("empty")
        assert result == "(empty)"


# ---------------------------------------------------------------------------
# run_compilation
# ---------------------------------------------------------------------------

class TestRunCompilationTool:
    @patch("subprocess.run")
    def test_returns_success_message_when_returncode_zero(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        tools = make_tools(tmp_path, [])
        run_compilation = _get_tool(tools, "run_compilation")

        result = run_compilation()
        assert result == "Compilation succeeded."

    @patch("subprocess.run")
    def test_returns_error_lines_when_compilation_fails(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="src/Comp.vue(5,3): error TS2304: Cannot find name 'computed'.\n",
            stderr="",
        )
        tools = make_tools(tmp_path, [])
        run_compilation = _get_tool(tools, "run_compilation")

        result = run_compilation()
        assert "error TS2304" in result
        assert result != "Compilation succeeded."

    @patch("subprocess.run")
    def test_only_returns_error_lines_not_full_stdout(self, mock_run, tmp_path):
        """Should filter stdout to only error lines — keeps context window lean."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=(
                "vite v5.0.0 building...\n"
                "src/Comp.vue(5,3): error TS2304: Cannot find name 'computed'.\n"
                "Found 1 error.\n"
            ),
            stderr="",
        )
        tools = make_tools(tmp_path, [])
        run_compilation = _get_tool(tools, "run_compilation")

        result = run_compilation()
        assert "error TS2304" in result
        assert "vite v5.0.0" not in result

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("npm", 60))
    def test_returns_error_on_timeout(self, mock_run, tmp_path):
        tools = make_tools(tmp_path, [])
        run_compilation = _get_tool(tools, "run_compilation")

        result = run_compilation()
        assert result.startswith("ERROR:")
        assert "timeout" in result.lower() or "timed out" in result.lower()

    @patch("subprocess.run")
    def test_runs_npm_type_check_in_target_project(self, mock_run, tmp_path):
        """Compilation must run in the target_project directory."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        tools = make_tools(tmp_path, [])
        run_compilation = _get_tool(tools, "run_compilation")

        run_compilation()
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("cwd") == tmp_path or call_kwargs[1].get("cwd") == tmp_path
