# Results JSON Schema

This document describes the structure of the JSON files saved under `results/published/`. All field names are `snake_case`.

---

## Folder layout

```
results/published/
└── session__{name}__{unix_timestamp}/
    └── {model_folder}/
        ├── {model_folder}__{fixture}__{iso_timestamp}.json        # single-shot (A, F)
        └── {model_folder}__{fixture}__{n}runs__{unix_timestamp}/
            └── summary.json                                        # agent (B–E, G–J)
```

**Model folder naming**: `:` in model names is replaced by `__`.
Examples: `qwen3.5:35b` → `qwen3.5__35b`, `qwen3.5:35b-a3b` → `qwen3.5__35b-a3b`.

---

## Single-shot format

The file is a **JSON array** of Run objects — one entry per run.

```json
[
  { ...run },
  { ...run }
]
```

---

## Agent format

The file is a **JSON object** with a top-level `runs` array.

```json
{
  "model":   "qwen3.5:35b",
  "fixture": "nuxt-form-agent-guided",
  "n_runs":  10,
  "prompt":  "...",
  "runs":    [ { ...run }, { ...run } ]
}
```

| Field    | Type   | Description |
|----------|--------|-------------|
| `model`  | string | Ollama model name (original, with `:`) |
| `fixture`| string | Task name (e.g. `nuxt-form-agent-guided`) |
| `n_runs` | int    | Total number of runs attempted |
| `prompt` | string | Full prompt sent to the model (includes injected API docs) |
| `runs`   | array  | Per-run results (see Run object below) |

---

## Run object

Fields present in both single-shot and agent runs.

| Field                  | Type            | Description |
|------------------------|-----------------|-------------|
| `model`                | string          | Ollama model name |
| `fixture`              | string          | Task name |
| `timestamp`            | string (ISO)    | Run start time |
| `run_number`           | int             | 1-based index within this fixture/model pair |
| `compiles`             | bool            | TypeScript compilation passed |
| `compilation_errors`   | string[]        | Raw `vue-tsc` error lines (empty when `compiles: true`) |
| `compilation_warnings` | string[]        | Raw `vue-tsc` warning lines |
| `pattern_score`        | float (0–10)    | Regex pattern check score |
| `ast_checks`           | object          | Per-check boolean results (keys vary by battery — see below) |
| `ast_missing`          | string[]        | Names of checks that failed |
| `naming_score`         | float (0–10)    | Naming convention score |
| `naming_violations`    | string[]        | Variable/interface names that violated conventions |
| `final_score`          | float (0–10)    | Weighted composite score |
| `scoring_weights`      | object          | Weights used: `{ compilation, pattern_match, naming }` |
| `tokens_per_sec`       | float           | Generation speed reported by Ollama |
| `duration_sec`         | float           | Wall-clock time for the full run |
| `output_code`          | string          | Final generated file content (last written version) |
| `errors`               | string[]        | Non-compilation errors (e.g. validation exceptions) |

### Agent-only fields

| Field           | Type    | Description |
|-----------------|---------|-------------|
| `steps`         | int     | Tool-calling turns used (`final_answer` is logged but not counted) |
| `max_steps`     | int     | Hard cap from `validation_spec.json` |
| `iterations`    | int     | Total `write_file` + `run_compilation` calls combined |
| `succeeded`     | bool    | Agent finished before reaching `max_steps` |
| `aborted`       | bool    | `true` if `agent.run()` raised an exception (e.g. Ollama 500) — **exclude from aggregates** |
| `tool_call_log` | array   | Ordered log of every tool call (see below) |

---

## `tool_call_log` entry

Each entry represents one tool call made by the agent.

```json
{
  "step":           2,
  "tool":           "run_compilation",
  "args":           {},
  "result_summary": "(see latest compilation result)",
  "compile_passed": false,
  "duration_sec":   103.24,
  "context_chars":  28750
}
```

| Field            | Type          | Description |
|------------------|---------------|-------------|
| `step`           | int           | Step number within the agent run |
| `tool`           | string        | Tool name: `write_file`, `run_compilation`, `read_file`, `list_files`, `query_rag`, `final_answer` |
| `args`           | object        | Arguments passed to the tool (pruned for large content) |
| `result_summary` | string        | Abbreviated tool result (`"File written."`, `"(see latest compilation result)"`, etc.) |
| `compile_passed` | bool \| null  | `true`/`false` for `run_compilation`; **`null` for all other tools** |
| `duration_sec`   | float         | Time taken by this tool call |
| `context_chars`  | int           | Total context window size (chars) after this step |

`final_answer` entries are included for diagnostics but do **not** contribute to `steps`.

---

## `ast_checks` keys

`ast_checks` is an **object** mapping check name → bool (not an array).

**Battery 1 — Form (A→E):**
```json
{
  "script_lang":          true,
  "form_component":       true,
  "controlled_components": true,
  "conditional_rendering": true,
  "zod_schema":           true,
  "required_fields":      true,
  "conditional_fields":   true
}
```

**Battery 2 — DataTable (F→J):**
```json
{
  "script_lang":       true,
  "datatable_component": true,
  "render_function":   true,
  "currency_formatter": true,
  "date_formatter":    true,
  "status_badge":      true,
  "action_handlers":   true,
  "column_ids":        true
}
```

---

## Common gotchas

- **Aborted runs**: filter `runs` where `aborted === true` before computing averages. Aborted runs have all scores set to `0` and no valid output.
- **`compile_passed` is `null` for non-compilation tools**: only `run_compilation` entries have `true`/`false`.
- **`ast_checks` is an object**, not an array. Iterate with `Object.entries()` (JS) or `.items()` (Python).
- **Model name encoding**: `:` → `__` in folder/file names. Reverse with `.replace('__', ':', 1)`.
- **Single-shot vs agent root shape**: single-shot files are bare arrays; agent `summary.json` files wrap runs in an object. Check for `Array.isArray()` (JS) or `isinstance(data, list)` (Python) to distinguish them.

---

## Python loading example

```python
import json
from pathlib import Path

def load_runs(session_dir: Path) -> list[dict]:
    """Load all runs from a published session folder."""
    runs = []
    for json_file in session_dir.rglob("*.json"):
        data = json.loads(json_file.read_text())
        if isinstance(data, list):
            # single-shot: bare array of runs
            runs.extend(data)
        elif isinstance(data, dict) and "runs" in data:
            # agent: object with runs[]
            runs.extend(data["runs"])
    return runs

session = Path("results/published/session__my-comparison__1234567890")
runs = load_runs(session)

# Filter out aborted runs before aggregating
valid = [r for r in runs if not r.get("aborted")]

# Example: average final_score per fixture
from collections import defaultdict
by_fixture = defaultdict(list)
for r in valid:
    by_fixture[r["fixture"]].append(r["final_score"])

for fixture, scores in sorted(by_fixture.items()):
    print(f"{fixture}: {sum(scores)/len(scores):.2f} (n={len(scores)})")
```
