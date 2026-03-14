# LLM Benchmark Suite

**Project**: Local LLM Benchmarking Tool for Vue.js/Nuxt/TypeScript Development

---

## Objective

Benchmark LLMs locally via Ollama against two diagnostic batteries — **form (A→E)** and **DataTable (F→J)** — totalling 10 tasks targeting a shared Nuxt Turborepo monorepo. Each task changes exactly one variable vs the previous, isolating the model's capability boundary. The tool executes tasks, validates TypeScript compilation and pattern conformance, and collects metrics (scores, tokens/sec, duration, steps).

---

## Development Workflow & Rules of Engagement

### Fundamental Principle
Our workflow is dynamic: **Initial Plan ➔ Step-by-step Execution with Revision possibility for each step ➔ Final Approval in the CLI**.

### Code Quality Standards
Before generating code:
- If you see suboptimal approaches, propose them
- If critical info is missing, ask for it
- If the request is ambiguous, explore alternatives
- Don't generate code "because you asked me to" if it's clearly wrong

Red flags to report:
- Duplication of existing logic
- Patterns that violate codebase conventions
- Avoidable complexity

### Test-Driven Development (TDD)
- **All tests must be implemented BEFORE the actual function implementation**
- Follow the TDD cycle: Red → Green → Refactor

#### Test file conventions

All tests live flat in `tests/` — no subdirectories. Naming: `test_{module_snake_case}_{aspect}.py`.

Each task gets two test files:
- `test_<task>_validator.py` — covers `validate_ast_structure`, `validate_compilation`, `validate_naming`
- `test_<task>_runner.py` — covers `CreationTest` / `AgentTest` orchestration (uses mocks)

RAG tasks also get `test_<task>_rag.py` for `QueryRagTool`.

Shared modules: `test_run_test.py` (CLI entry point), `test_agent_client.py`, `test_ollama_client.py`.

#### What to test

**Validator tests**: define a `COMPLETE_COMPONENT` string constant at module level with a fully correct fixture. Then test each validation function against it and against targeted broken variants (missing pattern, wrong naming, etc.). Keep fixtures as inline strings — no file I/O.

**Runner tests**: use `@dataclass` stubs and `unittest.mock` patches. Never call Ollama. Test that `format_run()` doesn't crash, that `save_results()` writes the expected JSON keys, and that fixture resolution paths are correct.

**Integration tests**: mark with `@pytest.mark.integration`. These require a live Ollama instance and will fail without one — this is expected. CI (`pytest -m "not integration"`) skips them.

### Bug Fix Workflow
When fixing a bug:
1. Determine the root cause and identify what needs to change
2. **Write or update a test** that reproduces the broken case — it must **fail before the fix**
3. Implement the fix
4. Verify the test passes and no other tests regress

Regression tests should include a docstring comment explaining what bug they guard against (see `test_run_test.py` for examples: `test_default_parameter_is_tasks_dir` guards against the `FIXTURES_BASE → TASKS_DIR` rename bug).

### Development Environment
- Python virtual environment managed with `venv`
- Activate environment using the alias: `llmbench`

---

## Project Structure

```
~/Projects/llm-benchmark/
├── venv/
├── requirements.txt               # ollama, rich, smolagents[openai], rank-bm25
├── CLAUDE.md
├── README.md
│
├── src/
│   ├── common/
│   │   └── ollama_client.py       # Shared Ollama API wrapper
│   ├── creation/
│   │   ├── nuxt_form_oneshot/
│   │   │   ├── test_runner.py     # CreationTest + BenchmarkResult (Test A)
│   │   │   └── validator.py       # Regex-based validation
│   │   └── nuxt_dt_oneshot/
│   │       ├── test_runner.py     # CreationTest + BenchmarkResult (Test F)
│   │       └── validator.py
│   └── agent/
│       ├── common/
│       │   └── agent_client.py    # run_agent() → AgentRunResult (extra_system_prompt param)
│       ├── nuxt_form_agent_guided/
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation ONLY (Test B)
│       │   └── validator.py
│       ├── nuxt_form_agent_twofiles/
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation, 2 files (Test C)
│       │   └── validator.py
│       ├── nuxt_form_agent_rag/
│       │   ├── rag.py             # QueryRagTool (rag_docs_path from validation_spec)
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation + query_rag (Test D)
│       │   └── validator.py
│       ├── nuxt_form_agent_full/
│       │   ├── rag.py             # QueryRagTool (BM25Plus over shared rag_docs)
│       │   ├── test_runner.py     # AgentTest — full tools + RAG (Test E)
│       │   └── validator.py
│       ├── nuxt_dt_agent_guided/
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation (Test G)
│       │   └── validator.py
│       ├── nuxt_dt_agent_twofiles/
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation, 2 files (Test H)
│       │   └── validator.py
│       ├── nuxt_dt_agent_rag/
│       │   ├── rag.py             # QueryRagTool (rag-docs-vue-elements-datatable)
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation + query_rag (Test I)
│       │   └── validator.py
│       └── nuxt_dt_agent_full/
│           ├── rag.py             # QueryRagTool (BM25Plus over rag-docs-vue-elements-datatable)
│           ├── test_runner.py     # AgentTest — full tools + RAG (Test J)
│           └── validator.py
│
├── scripts/
│   └── parse_vue_ast.js           # Node.js AST parser (@vue/compiler-sfc + Babel)
│
├── fixtures/
│   └── _shared/
│       ├── turborepo-nuxt-vue-elements/        # Turborepo monorepo (apps/web + packages/elements)
│       ├── rag-docs-vue-elements-form/         # 5 BM25-indexed form example files (shared by D and E)
│       └── rag-docs-vue-elements-datatable/    # 5 BM25-indexed DataTable example files (shared by I and J)
│
├── results/
│   └── published/                 # Versioned results (gitignored except session__* folders)
│       └── session__*/            # Committed via explicit `git add`
│
├── dashboard/                     # Nuxt 4 SSG dashboard
│   ├── app/
│   │   ├── pages/
│   │   │   ├── index.vue                                    # Sessions list
│   │   │   └── sessions/[sessionName]/
│   │   │       ├── index.vue                                # Comparison + model selector
│   │   │       └── [modelName]/
│   │   │           ├── index.vue                            # Model detail (fixture × run table)
│   │   │           └── [fixtureName]/
│   │   │               ├── index.vue                        # Fixture detail (per-run cards)
│   │   │               └── [runNumber].vue                  # Run detail (full data)
│   │   └── components/
│   │       ├── ScoreBar.vue                                 # Colored score bar (0-10)
│   │       └── Breadcrumb.vue                               # Navigation breadcrumb
│   └── server/api/
│       ├── manifest.get.ts                                  # List published sessions
│       └── sessions/
│           ├── [name].get.ts                                # Session comparison aggregates
│           └── [name]/
│               ├── [model].get.ts                           # Model fixtures + run summaries
│               └── [model]/
│                   ├── [fixture].get.ts                     # Fixture runs (no output_code)
│                   └── [fixture]/[run].get.ts               # Single run (full, with output_code)
│
├── tasks/                         # One directory per task (flat)
│   ├── nuxt-form-oneshot/         # Test A — single-shot, full context inline
│   │   ├── prompt.md              # default prompt
│   │   ├── prompt-v2.md           # corrected prompt (no defineProps fix)
│   │   └── validation_spec.json   # target_project_path → ../../fixtures/_shared/turborepo-nuxt-vue-elements
│   ├── nuxt-form-agent-guided/    # Test B — write+compile, 1 file
│   │   ├── prompt.md
│   │   └── validation_spec.json   # target_project_path, max_steps: 10
│   ├── nuxt-form-agent-twofiles/  # Test C — write+compile, 2 files
│   │   ├── prompt.md
│   │   ├── prompt-v2.md
│   │   └── validation_spec.json   # target_project_path, max_steps: 15
│   ├── nuxt-form-agent-rag/       # Test D — write+compile+RAG (no read)
│   │   ├── prompt.md
│   │   └── validation_spec.json   # target_project_path, rag_docs_path, max_steps: 20
│   ├── nuxt-form-agent-full/      # Test E — full agent (read/write/list/compile/RAG)
│   │   ├── prompt.md
│   │   ├── prompt-v2.md
│   │   ├── prompt-v3.md
│   │   └── validation_spec.json   # target_project_path, rag_docs_path, max_steps: 30
│   ├── nuxt-dt-oneshot/           # Test F — single-shot, full context inline
│   │   ├── prompt.md
│   │   └── validation_spec.json   # target_file: apps/web/src/orders/OrdersDataTable.vue
│   ├── nuxt-dt-agent-guided/      # Test G — write+compile, 1 file
│   │   ├── prompt.md
│   │   └── validation_spec.json   # target_project_path, max_steps: 10
│   ├── nuxt-dt-agent-twofiles/    # Test H — write+compile, 2 files (columns.ts + OrdersDataTable.vue)
│   │   ├── prompt.md
│   │   └── validation_spec.json   # target_project_path, max_steps: 15
│   ├── nuxt-dt-agent-rag/         # Test I — write+compile+RAG (no read)
│   │   ├── prompt.md
│   │   └── validation_spec.json   # target_project_path, rag_docs_path, max_steps: 20
│   └── nuxt-dt-agent-full/        # Test J — full agent (read/write/list/compile/RAG)
│       ├── prompt.md
│       └── validation_spec.json   # target_project_path, rag_docs_path, max_steps: 30
│
├── tests/
├── results/                       # gitignored, created at runtime
└── run_test.py                    # CLI entry point
```

---

## Dashboard

Nuxt 4 SSG app in `dashboard/`. Reads `results/published/` at build time via server API routes; all aggregations happen server-side. Client receives only pre-computed JSON.

```bash
cd dashboard && npm run dev               # dev server (SSR)
npm run generate-preview                  # static build + preview (closest to production)
npm run generate                          # static build only
NUXT_APP_BASE_URL=/llm-benchmark/ npm run generate  # GitHub Pages
```

**Route structure** (no wrapper `.vue` files — each directory uses `index.vue`):
- `/` — sessions list
- `/sessions/[sessionName]` — comparison table with model selector (default: first 2, max 4)
- `/sessions/[sessionName]/[modelName]` — per-fixture run table for one model
- `/sessions/[sessionName]/[modelName]/[fixtureName]` — per-run cards with tool call log / AST checks
- `/sessions/[sessionName]/[modelName]/[fixtureName]/[runNumber]` — full run detail

**SSG crawler**: only pre-renders pages reachable via `<a>` tags. The session comparison page includes a hidden `<nav aria-hidden="true">` with `NuxtLink` elements for all models to ensure every model detail page is pre-rendered.

**GitHub Actions**: `.github/workflows/deploy.yml` deploys to GitHub Pages (manual `workflow_dispatch` only). `.github/workflows/ci.yml` runs `pytest -m "not integration"` on push/PR to main.

**Publishing results**: copy a session folder to `results/published/`, then `git add results/published/session__*` and commit. Alternatively, use `--publish` flag with `run_test.py` to save directly to `results/published/`.

---

## Architecture

### Validation Pipeline

```
LLM Output
    ↓
[1] TypeScript Compilation (vue-tsc via npm run check-types from apps/web/)
    ↓
[2] Pattern Matching (Python regex on component source)
    ↓
[3] Naming Convention Check (Python regex on variable declarations)
    ↓
Composite Score (0–10)
```

Scoring weights come from each task's `validation_spec.json` (default: compilation 50%, pattern 40%, naming 10%).

### Task categories

**Single-shot** (Tests A, F) — one prompt → one response → validation.
- `CreationTest` in `src/creation/<task_name>/test_runner.py`
- Validation: TypeScript compilation + regex pattern checks + naming conventions
- Score: 0–10 composite

**Agent** (Tests B–E, G–J) — multi-turn: the model calls tools (read/write/compile) in a loop, receives feedback, and iterates.
- `AgentTest` in `src/agent/<module>/test_runner.py`
- Uses smolagents `ToolCallingAgent` + `OpenAIServerModel` → Ollama `/v1`
- `max_steps` (from `validation_spec.json`) is the hard cap via smolagents
- `iterations` (count of `write_file` + `run_compilation` calls) is an observational metric
- JSON format rules injected into the smolagents system prompt at each step to help small models
- `write_file` and `run_compilation` are **decoupled**: `write_file` only writes and returns `"File written."`, the model must call `run_compilation` separately for TS feedback
- `run_crashed` in `AgentRunResult`: set when `agent.run()` raises (e.g. Ollama 500); `aborted` in `AgentBenchmarkResult`: all scores → 0, validation skipped, run excluded from dashboard aggregates
- `final_answer` steps are logged in `tool_call_log` for diagnostics but do NOT increment `step_count`; `_COMPILE_TOOLS = {"run_compilation"}` only

### Per-task layout

Each task has its own `test_runner.py` and `validator.py` in `src/`. Duplication is intentional — task-specific logic diverges enough to make shared abstractions premature.

Each `test_runner.py` exposes `format_run(result) -> None` for per-run console output. No display logic lives in `run_test.py`.

### [run_test.py](run_test.py) — CLI entry point

```
python run_test.py --model <model> [--fixture <name>] [--runs <n>] [--publish] [--prompt-override TASK=VERSION ...]
```

- `--publish`: saves session directly to `results/published/` instead of `results/`
- `--prompt-override TASK=VERSION`: uses `prompt-{VERSION}.md` instead of `prompt.md` for the specified task (e.g. `nuxt-form-oneshot=v2`). Multiple overrides can be specified.
- `_get_runner_class()` checks for `AgentTest` first, then `CreationTest`.
- All runner `__init__` methods accept `prompt_version: str | None = None`; they resolve `prompt-{version}.md` if set.

New tasks must be registered in `_RUNNER_MAP` in [run_test.py](run_test.py).

---

## Key Technical Notes

- **Graceful degradation**: AST/naming validation exceptions produce score=0 result, never crash the run loop.
- **File restoration**: always happens in a `finally` block in `test_runner.py`.
- **`OLLAMA_BASE_URL`** env var overrides the default Ollama host.
- **`target_project_path`** in `validation_spec.json`: resolves relative to the task dir. All tasks point to `../../fixtures/_shared/turborepo-nuxt-vue-elements`.
- **`rag_docs_path`** in `validation_spec.json`: same mechanism for RAG docs path override. Tasks D and E point to `../../fixtures/_shared/rag-docs-vue-elements-form`.
- **`extra_system_prompt`** in `run_agent()`: appended to the smolagents system prompt after construction; used for soft tool-usage reminders (e.g. RAG reminder) without overriding FORMAT_REMINDER.
- **`compilation_cwd`** and **`compilation_command`** in `validation_spec.json`: used for the Turborepo monorepo where `npm run check-types` must run from `apps/web/`.
- **`write_file` is decoupled from compilation**: it only writes and returns `"File written."`. The model must call `run_compilation` explicitly to receive TS error feedback.
- **Aborted runs**: if `agent.run()` raises (e.g. Ollama 500), `AgentRunResult.run_crashed=True` → `AgentBenchmarkResult.aborted=True`, all scores set to 0, validation skipped. Dashboard `aggregateRuns()` filters aborted runs before computing averages and reports `n_aborted`.
- **`final_answer` in `tool_call_log`**: logged as a diagnostic entry but excluded from `step_count`. `_COMPILE_TOOLS = {"run_compilation"}` only — `compile_passed` is `None` for `write_file` entries.
- **FormFields slot**: `inject()` returns `T | undefined` by default. The `form-fields.vue` component uses `inject<FormContext>(...)!` (non-null assertion) so consumers can use `form.values.field` directly without `?.`. Models should NOT add `?.` inside `<FormFields>`.
- **FormActions slot**: `form` prop is `FormContext | undefined` — use `form?.isSubmitting.value`.
- **Controlled components** (`ControlledInput`, `ControlledRadioGroup`, etc.) receive `form` via `provide/inject` — do NOT pass `:form="form"` as a prop.
- **BM25 RAG**: use `BM25Plus` (not `BM25Okapi`) to avoid negative IDF on small corpora.
- **`form_component` check**: uses `<Form(?=[\s\n>])` to avoid matching `<FormWrapper` etc. as false positives.
- **DataTable target file**: `apps/web/src/orders/OrdersDataTable.vue`. Test J has 3 writable files: `types.ts`, `columns.ts`, `OrdersDataTable.vue` (all under `apps/web/src/orders/`).
- **Column renderers**: use Vue's `h()` render function (not JSX) — imported from `vue`. Required for currency/date formatters and the status badge cell.
- **DataTable RAG docs**: `rag-docs-vue-elements-datatable/` shared by Tests I and J (analogous to `rag-docs-vue-elements-form/` for D and E).

---

## Adding a New Task

> **Naming convention**: task directories use kebab-case (`my-task`), Python modules use snake_case (`my_task`). The mapping is explicit in `_RUNNER_MAP`.

### Single-shot task
1. Create `tasks/<task-name>/` with `prompt.md`, `validation_spec.json` (`target_project_path` relative to task dir)
2. Create `src/creation/<task_name>/` with `__init__.py`, `test_runner.py`, `validator.py`
3. Register in [run_test.py](run_test.py) `_RUNNER_MAP`
4. Write tests first (TDD)

### Agent task
1. Create `tasks/<task-name>/` with `prompt.md`, `validation_spec.json` (include `max_steps`, `target_project_path`)
2. Create `src/agent/<task_name>/` with `__init__.py`, `test_runner.py` (`AgentTest` + `AgentBenchmarkResult`), `validator.py`
3. Register in [run_test.py](run_test.py) `_RUNNER_MAP`
4. Write tests first (TDD)

**RAG variant**: if the task needs a `query_rag` tool, also add:
- `rag_docs_path` in `validation_spec.json` (point to `../../fixtures/_shared/rag-docs-vue-elements-form` or a new docs dir)
- `src/agent/<task_name>/rag.py` — `QueryRagTool(Tool)` using `BM25Plus` (not BM25Okapi)
- `compilation_cwd` and `compilation_command` in `validation_spec.json` if non-standard

---

## Dependencies

- Python 3.12+, `ollama>=0.4.0`, `rich>=13.0.0`, `smolagents[openai]>=1.0.0`, `rank-bm25>=0.2.2`
- Node.js 24.x
- Ollama running with a loaded model
- Shared monorepo: `npm install --prefix fixtures/_shared/turborepo-nuxt-vue-elements`
