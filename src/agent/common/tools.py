"""Agent tools for coding benchmark fixtures.

Factory: make_tools(target_project, allowed_paths) → list of @tool callables.

All file operations are relative to target_project and enforce the
allowed_paths whitelist. Path traversal is blocked via Path.resolve().
"""

import subprocess
from pathlib import Path
from typing import List

from smolagents import tool


def make_tools(target_project: Path, allowed_paths: List[str]) -> List:
    """Return smolagents tool functions bound to the given project path.

    Args:
        target_project: Absolute path to the fixture's target_project directory.
        allowed_paths: Relative paths the agent is permitted to write to.

    Returns:
        List of @tool-decorated callables ready to pass to ToolCallingAgent.
    """
    target_project = target_project.resolve()
    resolved_root = target_project
    allowed_write_set = set(allowed_paths)

    def _safe_resolve(relative_path: str) -> Path:
        """Resolve a relative path inside target_project, raising ValueError on traversal."""
        full = (target_project / relative_path).resolve()
        full.relative_to(resolved_root)  # raises ValueError if outside
        return full

    @tool
    def read_file(path: str) -> str:
        """Read a file from the project.

        Args:
            path: Relative path to the file (e.g. 'src/components/BuggyComponent.vue').

        Returns:
            File contents as a string, or an error message starting with 'ERROR:'.
        """
        try:
            full = _safe_resolve(path)
            return full.read_text()
        except ValueError:
            return f"ERROR: Path '{path}' is outside the project directory."
        except FileNotFoundError:
            return f"ERROR: File not found: {path}"
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file in the project, then run TypeScript compilation.

        Only paths in the fixture's allowed_write_paths may be written.
        Compilation runs automatically after every write — no separate
        run_compilation call is needed.

        Args:
            path: Relative path to write (e.g. 'src/components/BuggyComponent.vue').
            content: Complete file content to write.

        Returns:
            'File written.\\nCompilation succeeded.' on full success,
            'File written.\\nCompilation errors:\\n{errors}' if TS errors remain,
            or an error message starting with 'ERROR:' if the write itself failed.
        """
        if path not in allowed_write_set:
            return (
                f"ERROR: Writing to '{path}' is not permitted. "
                f"Allowed: {sorted(allowed_write_set)}"
            )
        try:
            full = _safe_resolve(path)
            full.parent.mkdir(parents=True, exist_ok=True)
            # Defensive: some models over-escape JSON strings, producing literal
            # backslash+n/t instead of real control characters. Normalize here so
            # the written file is valid source code regardless.
            content = content.replace("\\n", "\n").replace("\\t", "\t")
            full.write_text(content)
        except ValueError:
            return f"ERROR: Path '{path}' is outside the project directory."
        except Exception as e:
            return f"ERROR: {e}"

        # Auto-compile after every write so the model gets immediate feedback.
        if not (resolved_root / "package.json").exists():
            return "File written. (Compilation skipped: no package.json found.)"

        try:
            result = subprocess.run(
                ["npm", "run", "type-check"],
                cwd=resolved_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return "File written.\nCompilation succeeded."
            combined = result.stdout + "\n" + result.stderr
            error_lines = [
                line.strip()
                for line in combined.split("\n")
                if "error TS" in line or " - error" in line
            ]
            errors = "\n".join(error_lines) if error_lines else combined.strip()
            return f"File written.\nCompilation errors:\n{errors}"
        except subprocess.TimeoutExpired:
            return "File written.\nERROR: Compilation timed out after 60 seconds."
        except Exception as e:
            return f"File written.\nERROR: Compilation check failed: {e}"

    @tool
    def list_files(directory: str = ".") -> str:
        """List files in a project directory (excludes node_modules and .git).

        Args:
            directory: Relative path to directory (default: '.' for project root).

        Returns:
            Newline-separated list of relative file paths, or an error message.
        """
        try:
            full = _safe_resolve(directory)
            if not full.is_dir():
                return f"ERROR: '{directory}' is not a directory."
            entries = sorted(
                str(p.relative_to(target_project))
                for p in full.rglob("*")
                if p.is_file()
                and "node_modules" not in p.parts
                and ".git" not in p.parts
            )
            return "\n".join(entries) if entries else "(empty)"
        except ValueError:
            return f"ERROR: Path '{directory}' is outside the project directory."
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def run_compilation() -> str:
        """Run TypeScript compilation (vue-tsc) and return errors.

        Returns:
            'Compilation succeeded.' if clean, otherwise the TypeScript error lines.
        """
        try:
            result = subprocess.run(
                ["npm", "run", "type-check"],
                cwd=target_project,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return "Compilation succeeded."
            combined = result.stdout + "\n" + result.stderr
            error_lines = [
                line.strip()
                for line in combined.split("\n")
                if "error TS" in line or " - error" in line
            ]
            return "\n".join(error_lines) if error_lines else combined.strip()
        except subprocess.TimeoutExpired:
            return "ERROR: Compilation timed out after 60 seconds."
        except Exception as e:
            return f"ERROR: {e}"

    return [read_file, write_file, list_files, run_compilation]
