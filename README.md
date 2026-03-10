# LLM Benchmark Suite

Local benchmarking tool for testing LLM performance on Vue.js/Nuxt/TypeScript development tasks using Ollama.

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Benchmark](#running-the-benchmark)
- [Tasks](#tasks)
- [Scoring](#scoring)
- [Project Structure](#project-structure)
- [Development](#development)
  - [Running Tests](#running-tests)
  - [Adding a New Task](#adding-a-new-task)
  - [Dashboard](#dashboard)
  - [Environment Variables](#environment-variables)

## Overview

Benchmarks LLMs on a diagnostic battery of **5 tasks** (A→E) targeting the same Nuxt monorepo. Each test changes exactly one variable vs the previous, isolating the model's capability boundary:

| Test | Task | Tools | Files | Docs | Variable |
|------|------|-------|-------|------|----------|
| A | `nuxt-form-oneshot` | — (single-shot) | 1 | inline | baseline |
| B | `nuxt-form-agent-guided` | write + compile | 1 | inline | iterative TS feedback |
| C | `nuxt-form-agent-twofiles` | write + compile | 2 | inline | two-file dependency chain |
| D | `nuxt-form-agent-rag` | write + compile + RAG | 2 | none | autonomous retrieval |
| E | `nuxt-form-agent-full` | read + write + list + compile + RAG | 2 | none | filesystem exploration |

All tasks share a single **Turborepo monorepo** (`fixtures/_shared/turborepo-nuxt-vue-elements/`). Tasks D and E also share a **BM25 RAG index** (`fixtures/_shared/rag-docs-vue-elements-form/`).

Single-shot (Test A) validates the LLM response with TypeScript compiler (`vue-tsc`) and pattern checks, scoring on compilation success, pattern conformance, and naming conventions. Agent tasks (B–E) additionally track steps used and compilation attempts.

## Requirements

- Python 3.12+
- Node.js 24.x
- Ollama running locally (or via `OLLAMA_BASE_URL`)

## Installation

```bash
git clone <repo>
cd llm-benchmark

# Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node.js AST parser dependencies (project root)
npm install

# Shared monorepo dependencies (needed by all tasks)
npm install --prefix fixtures/_shared/turborepo-nuxt-vue-elements
```

## Configuration

Optional: set `OLLAMA_BASE_URL` to point to a remote Ollama instance.

```bash
# .env (gitignored)
OLLAMA_BASE_URL=http://192.168.1.100:11434
```

## Running the Benchmark

```bash
source venv/bin/activate

# Run all tasks with a single model (3 runs each)
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0

# Run all tasks on multiple models in series, grouped in a named session
python run_test.py --models qwen2.5-coder:7b-instruct-q8_0 qwen2.5-coder:14b-instruct-q8_0 \
  --session-name my-comparison

# Run a specific task
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --fixture nuxt-form-oneshot

# Change number of runs
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --runs 5
```

Results are saved to `results/` (gitignored by default):
```
results/session__{name}__{timestamp}/{model}/
```

To publish results directly to `results/published/` (ready for the dashboard), use `--publish`:
```bash
python run_test.py --models qwen2.5-coder:7b --session-name my-run --publish
```

Or copy manually afterwards:
```bash
cp -r results/session__my-comparison__* results/published/
```

### Alternate prompt versions

Each task uses `tasks/<task>/prompt.md` by default. To run with an alternate prompt (e.g. after a prompt fix), use `--prompt-override`:

```bash
# Run Task A with prompt-v2.md instead of prompt.md
python run_test.py --models qwen2.5-coder:7b \
  --prompt-override nuxt-form-oneshot=v2 \
  --session-name oneshot-prompt-v2 --publish

# Multiple overrides at once
python run_test.py --models qwen2.5-coder:7b \
  --prompt-override nuxt-form-oneshot=v2 nuxt-form-agent-guided=v2
```

Alternate prompt files follow the naming convention `prompt-{version}.md` inside the task directory. Sessions run with different prompts should use different `--session-name` values to keep results comparable.

## Tasks

### `nuxt-form-oneshot` (Test A)

Single-shot creation of a registration form in the Nuxt monorepo. All component API docs are injected inline in the prompt — no tools, no exploration, one response.

Max score: **10.0/10**.

### `nuxt-form-agent-guided` (Test B)

Agent with only `write_file` + `run_compilation` tools. Full API docs in the prompt — the model writes, compiles, and iterates using TypeScript error feedback. Same single-file task as Test A.

Max score: **10.0/10** — `max_steps: 10`.

### `nuxt-form-agent-twofiles` (Test C)

Same tool set as Test B, but the task now requires **two files in order**: `types/index.ts` (Zod schema + TS types) first, then `RegistrationForm.vue` importing from `@/registration/types`.

Max score: **10.0/10** — `max_steps: 15`.

### `nuxt-form-agent-rag` (Test D)

Agent with `write_file`, `run_compilation`, and `query_rag` tools. No docs in the prompt — the model must query the BM25 RAG index to discover the component API before writing.

Max score: **10.0/10** — `max_steps: 20`.

### `nuxt-form-agent-full` (Test E)

Full agent toolkit: `read_file`, `write_file`, `list_files`, `run_compilation`, `query_rag`. The model explores the monorepo filesystem autonomously, no API docs provided.

Target form: 7 fields, conditional logic (`role → otherInfo`, `newsletter → frequency`).
Two writable files: `RegistrationForm.vue` + `registration/types/index.ts`.
Compilation: `npm run check-types` from `apps/web/`.

Max score: **10.0/10** — `max_steps: 30`.

## Scoring

Each run produces a `final_score` (0–10) weighted across three dimensions:

| Dimension     | Weight | What it checks |
|---------------|--------|----------------|
| Compilation   | 50%    | TypeScript compilation passes without errors |
| Pattern match | 40%    | Required patterns present in the component |
| Naming        | 10%    | Variables/interfaces follow camelCase conventions |

Pattern checks (regex-based, applied to final file state):
- `lang="ts"` on script tag
- `<Form` component used
- Controlled components present (`ControlledInput`, `ControlledRadioGroup`, `ControlledCheckbox`, `ControlledTextarea`)
- `v-if` conditional rendering
- `z.object(` Zod schema
- All required fields (`username`, `email`, `role`, `bio`)
- Conditional fields (`newsletter`, `frequency`, `otherInfo`)

Agent tasks additionally track (not part of the score):

| Metric | Description |
|--------|-------------|
| `steps` | Total tool-calling turns used |
| `iterations` | Number of `write_file` + `run_compilation` calls combined |
| `succeeded` | True if agent finished before `max_steps` |

## Project Structure

```
llm-benchmark/
├── run_test.py                    # CLI entry point (argparse)
├── requirements.txt
├── package.json                   # Node.js AST parser deps (@vue/compiler-sfc)
│
├── src/
│   ├── common/
│   │   └── ollama_client.py       # Ollama API wrapper + metrics extraction
│   ├── creation/
│   │   └── nuxt_form_oneshot/
│   │       ├── test_runner.py     # CreationTest orchestrator + BenchmarkResult (Test A)
│   │       └── validator.py       # Regex-based validation
│   └── agent/
│       ├── common/
│       │   ├── tools.py           # make_tools() factory (read/write/list/compile)
│       │   └── agent_client.py    # run_agent() → AgentRunResult (smolagents wrapper)
│       ├── nuxt_form_agent_guided/
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation only (Test B)
│       │   └── validator.py
│       ├── nuxt_form_agent_twofiles/
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation, 2 files (Test C)
│       │   └── validator.py
│       ├── nuxt_form_agent_rag/
│       │   ├── rag.py             # QueryRagTool (BM25Plus, rag_docs_path from validation_spec)
│       │   ├── test_runner.py     # AgentTest — write_file + run_compilation + query_rag (Test D)
│       │   └── validator.py
│       └── nuxt_form_agent_full/
│           ├── rag.py             # QueryRagTool (BM25Plus over shared rag_docs)
│           ├── test_runner.py     # AgentTest — full tools + RAG (Test E)
│           └── validator.py
│
├── fixtures/
│   └── _shared/
│       ├── turborepo-nuxt-vue-elements/   # Turborepo monorepo (apps/web + packages/elements)
│       └── rag-docs-vue-elements-form/    # 5 BM25-indexed form example files (used by D and E)
│
├── tasks/                         # One directory per task — prompt.md + validation_spec.json
│   ├── nuxt-form-oneshot/         # Test A — prompt.md (default), prompt-v2.md (no-props fix)
│   ├── nuxt-form-agent-guided/    # Test B
│   ├── nuxt-form-agent-twofiles/  # Test C
│   ├── nuxt-form-agent-rag/       # Test D
│   └── nuxt-form-agent-full/      # Test E
│
├── scripts/
│   └── parse_vue_ast.js           # Node.js AST parser (@vue/compiler-sfc + Babel)
│
├── tests/                         # TDD test suite (validator + runner + shared tooling per task)
│
├── results/
│   └── published/                 # Versioned results (session__* folders committed)
│       └── session__*/            # One folder per published session
│
└── dashboard/                     # Nuxt 4 SSG dashboard
```

## Development

### Running Tests

```bash
source venv/bin/activate

# All tests
pytest

# Unit tests only (no Ollama required)
pytest -m "not integration"

# Verbose
pytest -v
```

Integration tests (marked `@pytest.mark.integration`) require a live Ollama instance with the model loaded. They will fail without the model — this is expected.

### Adding a New Task

> **Naming convention**: task directories use kebab-case (`my-task`), Python modules use snake_case (`my_task`). The mapping is explicit in `_RUNNER_MAP` in `run_test.py`.

#### Single-shot task

1. Create `tasks/<task-name>/` with:
   - `prompt.md` — full spec prompt (no template substitution)
   - `validation_spec.json` — `target_project_path` (relative to task dir), required patterns, naming conventions, scoring weights

2. Create `src/creation/<task_name>/` with:
   - `__init__.py`
   - `validator.py` — regex-based `validate_ast_structure()` and `validate_naming()`
   - `test_runner.py` — use `CreationTest` class (copy from `nuxt_form_oneshot/test_runner.py`)

3. Register in `run_test.py`:
   ```python
   _RUNNER_MAP = {
       ...
       "my-task-name": "src.creation.my_task_name.test_runner",
   }
   ```

4. Write tests first (TDD).

#### Agent task

1. Create `tasks/<task-name>/` with:
   - `prompt.md` — task description
   - `validation_spec.json` — `target_project_path`, `max_steps`, required patterns, naming conventions, scoring weights

2. Create `src/agent/<task_name>/` with:
   - `__init__.py`
   - `validator.py` — regex-based validation
   - `test_runner.py` — use `AgentTest` class (copy from an existing agent runner)

3. Register in `run_test.py`:
   ```python
   _RUNNER_MAP = {
       ...
       "my-task-name": "src.agent.my_task_name.test_runner",
   }
   ```

4. Write tests first (TDD).

**RAG variant**: if the task needs a `query_rag` tool, also add:
- `rag_docs_path` in `validation_spec.json` pointing to `../../fixtures/_shared/rag-docs-vue-elements-form` (or a new docs directory)
- `src/agent/<task_name>/rag.py` — `QueryRagTool(Tool)` using `BM25Plus` (not BM25Okapi)
- `compilation_cwd` and `compilation_command` in `validation_spec.json` if non-standard (e.g. Turborepo monorepo)

### Dashboard

`dashboard/` is a Nuxt 4 SSG app for exploring benchmark results. It reads `results/published/` at build time — all aggregations happen server-side; the client receives only pre-computed JSON.

**Pages:**
- **Sessions list** — all published sessions with model count and fixture coverage
- **Session comparison** — side-by-side fixture scores across up to 4 models (selectable pills); includes a problem description, fixture breakdown table (A→E tools/files/context/max-steps), and score legend
- **Model detail** — per-fixture run table with score, compile rate, pattern/naming scores, tok/s, duration, steps; fixture labels link directly to the fixture detail page
- **Fixture detail** — per-run cards showing tool call timeline (agent tasks) or AST check results + compilation errors (oneshot)
- **Run detail** — full data: agent meta grid (tokens, steps, iterations, RAG queries, file reads), tool call log with duration and context size, AST checks, naming violations, compilation errors, and the raw generated output

```bash
cd dashboard
npm install
npm run dev               # dev server on :3000 (SSR)
npm run generate-preview  # static build + preview (closest to production)
npm run generate          # static build only (reads ../results/published/)
```

To deploy to GitHub Pages set `NUXT_APP_BASE_URL=/llm-benchmark/` at build time. A GitHub Actions workflow (`.github/workflows/deploy.yml`) is available for manual deployment via `workflow_dispatch`.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `NUXT_APP_BASE_URL` | `/` | Base URL for the dashboard (set to `/llm-benchmark/` for GitHub Pages) |
