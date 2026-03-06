# LLM Benchmark Suite

**Project**: Local LLM Benchmarking Tool for Vue.js/Nuxt/TypeScript Development

---

## Objective

Benchmark LLMs locally via Ollama in controlled Vue.js project environments. The tool provides test fixtures (Vue 3 refactoring scenarios), executes LLM tasks, validates compilation and pattern conformance, and collects metrics (scores, tokens/sec, duration).

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

### Development Environment
- Python virtual environment managed with `venv`
- Activate environment using the alias: `llmbench`

---

## Project Structure

```
~/Projects/llm-benchmark/
├── venv/
├── requirements.txt               # ollama, rich, smolagents[openai]
├── CLAUDE.md
├── specs.md
├── README.md
│
├── src/
│   ├── common/
│   │   └── ollama_client.py       # Shared Ollama API wrapper
│   ├── refactoring/
│   │   ├── simple_component/
│   │   │   ├── test_runner.py     # RefactoringTest + BenchmarkResult
│   │   │   └── validator.py
│   │   └── typed_emits_composable/
│   │       ├── test_runner.py
│   │       └── validator.py
│   ├── creation/
│   │   ├── veevalidate_zod_form/
│   │   │   ├── test_runner.py     # CreationTest + BenchmarkResult
│   │   │   └── validator.py
│   │   └── nuxt_form_creation/
│   │       ├── test_runner.py     # CreationTest (target_project_path override, monorepo compile)
│   │       └── validator.py
│   └── agent/
│       ├── common/
│       │   ├── tools.py           # make_tools() factory (read/write/list/compile)
│       │   └── agent_client.py    # run_agent() → AgentRunResult (extra_system_prompt param)
│       ├── ts_bugfix/
│       │   ├── test_runner.py     # AgentTest + AgentBenchmarkResult
│       │   └── validator.py
│       ├── veevalidate_zod_form/
│       │   ├── test_runner.py     # AgentTest + AgentBenchmarkResult
│       │   └── validator.py
│       ├── veevalidate_zod_form_nuxt_rag/
│       │   ├── rag.py             # QueryRagTool (BM25Plus over rag_docs/)
│       │   ├── test_runner.py     # AgentTest + AgentBenchmarkResult
│       │   └── validator.py
│       ├── nuxt_form_agent_guided/
│       │   ├── test_runner.py     # AgentTest — tools: write_file + run_compilation ONLY
│       │   └── validator.py
│       └── nuxt_form_agent_rag/
│           ├── rag.py             # QueryRagTool (rag_docs_path from validation_spec)
│           ├── test_runner.py     # AgentTest — tools: write_file + run_compilation + query_rag
│           └── validator.py
│
├── scripts/
│   └── parse_vue_ast.js           # Node.js AST parser (@vue/compiler-sfc + Babel)
│
├── fixtures/
│   ├── refactoring/
│   │   ├── simple-component/
│   │   │   ├── target_project/    # Complete Vue 3 project (npm install done)
│   │   │   ├── prompt.md
│   │   │   └── validation_spec.json
│   │   └── typed-emits-composable/
│   │       ├── target_project/    # Complete Vue 3 project (npm install done)
│   │       ├── prompt.md
│   │       └── validation_spec.json
│   ├── creation/
│   │   ├── veevalidate-zod-form/
│   │   │   ├── target_project/
│   │   │   ├── prompt.md
│   │   │   └── validation_spec.json
│   │   └── nuxt-form-creation/        # Test A — single-shot, full context inline
│   │       ├── prompt.md
│   │       └── validation_spec.json   # target_project_path → veevalidate-zod-form-nuxt-rag/target_project
│   └── agent/
│       ├── ts-bugfix/
│       │   ├── target_project/    # Vue 3 project with intentionally broken component
│       │   ├── prompt.md
│       │   └── validation_spec.json
│       ├── veevalidate-zod-form-agent/
│       │   ├── target_project/    # Vue 3 project with intentional TS error stub
│       │   ├── prompt.md
│       │   └── validation_spec.json
│       ├── veevalidate-zod-form-nuxt-rag/   # Test D — full agent (read/write/compile/RAG)
│       │   ├── target_project/    # Turborepo monorepo (apps/web + packages/elements) — shared by A/B/C/D
│       │   ├── rag_docs/          # 5 form example files (BM25-indexed) — shared by C/D
│       │   ├── prompt.md
│       │   └── validation_spec.json
│       ├── nuxt-form-agent-guided/    # Test B — agent with write+compile only (no read/RAG)
│       │   ├── prompt.md
│       │   └── validation_spec.json   # target_project_path → veevalidate-zod-form-nuxt-rag/target_project
│       └── nuxt-form-agent-rag/       # Test C — agent with write+compile+RAG (no read)
│           ├── prompt.md
│           └── validation_spec.json   # target_project_path + rag_docs_path overrides
│
├── tests/
├── results/                       # gitignored, created at runtime
└── run_test.py                    # CLI entry point
```

---

## Architecture

### Validation Pipeline

```
LLM Output
    ↓
[1] TypeScript Compilation (vue-tsc via npm run type-check)
    ↓
[2] AST Pattern Matching (Node.js: @vue/compiler-sfc + Babel)
    ↓
[3] Naming Convention Check (Python regex on interface declarations)
    ↓
Composite Score (0–10)
```

Scoring weights come from each fixture's `validation_spec.json` (default: compilation 50%, pattern 40%, naming 10%).

### Fixture categories

**refactoring** and **creation** — single-shot: one prompt → one response → validation.
- `RefactoringTest` / `CreationTest` in each fixture's `test_runner.py`
- Validation: TypeScript compilation + AST/regex pattern checks + naming conventions
- Score: 0–10 composite

**agent** — multi-turn: the model calls tools (read/write/compile) in a loop, receives feedback, and iterates.
- `AgentTest` in `src/agent/<fixture>/test_runner.py`
- Uses smolagents `ToolCallingAgent` + `OpenAIServerModel` → Ollama `/v1`
- `max_steps` (from `validation_spec.json`) is the hard cap via smolagents
- `iterations` (count of `write_file` + `run_compilation` calls) is an observational metric
- JSON format rules injected into the smolagents system prompt at each step to help small models

### Per-fixture layout

Each fixture has its own `test_runner.py` and `validator.py`. Duplication is intentional — fixture-specific logic diverges enough to make shared abstractions premature.

Each `test_runner.py` exposes `format_run(result) -> None` for per-run console output. No display logic lives in `run_test.py`.

### [run_test.py](run_test.py) — CLI entry point

```
python run_test.py --model <model> [--fixture <name>] [--runs <n>]
```

`_get_runner_class()` checks for `RefactoringTest` first, then `AgentTest`, then `CreationTest`.

New fixtures must be registered in `_RUNNER_MAP` in [run_test.py](run_test.py).

---

## Key Technical Notes

- **AST parser**: `@vue/compiler-sfc` + Babel does not support TypeScript call signature syntax in emit interfaces. Use object-type syntax (`'event': [payload]`) — NOT call signatures (`('event': [payload]): void`).
- **`validate_naming()`**: supports both `interface_suffixes` (list, takes precedence) and `props_interface_suffix` (legacy string) in `naming_conventions`.
- **Graceful degradation**: AST/naming validation exceptions produce score=0 result, never crash the run loop.
- **File restoration**: always happens in a `finally` block in `test_runner.py`.
- **`OLLAMA_BASE_URL`** env var overrides the default Ollama host.
- **`target_project_path`** in `validation_spec.json`: resolves relative to the fixture dir, allows multiple fixtures to share one physical `target_project/` (e.g. the nuxt-form A/B/C/D battery all share `veevalidate-zod-form-nuxt-rag/target_project`).
- **`rag_docs_path`** in `validation_spec.json`: same mechanism for RAG docs path override (used by `nuxt-form-agent-rag` to reuse `veevalidate-zod-form-nuxt-rag/rag_docs`).
- **`extra_system_prompt`** in `run_agent()`: appended to the smolagents system prompt after construction; used for soft tool-usage reminders (e.g. RAG reminder) without overriding FORMAT_REMINDER.
- **FormFields slot**: `inject()` returns `T | undefined` by default. The `form-fields.vue` component uses `inject<FormContext>(...)!` (non-null assertion) so consumers can use `form.values.field` directly without `?.`. Models should NOT add `?.` inside `<FormFields>`.
- **FormActions slot**: `form` prop is `FormContext | undefined` — use `form?.isSubmitting.value`.
- **Controlled components** (`ControlledInput`, `ControlledRadioGroup`, etc.) receive `form` via `provide/inject` — do NOT pass `:form="form"` as a prop.

---

## Adding a New Fixture

> **Naming convention**: fixture directories use kebab-case (`my-fixture`), Python modules use snake_case (`my_fixture`). The mapping is explicit in `_RUNNER_MAP`.

### Refactoring / Creation fixture
1. Create `fixtures/<category>/<fixture-name>/` with `prompt.md`, `validation_spec.json`, `target_project/`
2. Run `npm install` in `target_project/`
3. Create `src/<category>/<fixture_name>/` with `__init__.py`, `test_runner.py`, `validator.py`
4. Register in [run_test.py](run_test.py) `_RUNNER_MAP`
5. Write tests first (TDD)

**Shared target_project**: to reuse an existing monorepo, set `target_project_path` in `validation_spec.json` (relative to fixture dir) instead of creating a new `target_project/`. No `npm install` needed.

### Agent fixture
1. Create `fixtures/agent/<fixture-name>/` with `prompt.md`, `validation_spec.json` (include `max_steps`), `target_project/`
2. Run `npm install` in `target_project/`; ensure `npm run type-check` (or equivalent) is configured
3. Create `src/agent/<fixture_name>/` with `__init__.py`, `test_runner.py` (`AgentTest` + `AgentBenchmarkResult`), `validator.py`
4. Register in [run_test.py](run_test.py) `_RUNNER_MAP`
5. Write tests first (TDD)

**RAG variant**: if the fixture needs a `query_rag` tool, also add:
- `fixtures/agent/<fixture-name>/rag_docs/` — one file per pattern (code-only, BM25-indexed); or set `rag_docs_path` in `validation_spec.json` to reuse existing docs
- `src/agent/<fixture_name>/rag.py` — `QueryRagTool(Tool)` using `BM25Plus` (not BM25Okapi)
- `compilation_cwd` and `compilation_command` in `validation_spec.json` if the project uses a non-standard compile command or working directory (e.g. Turborepo monorepo)

---

## Dependencies

- Python 3.12+, `ollama>=0.4.0`, `rich>=13.0.0`, `smolagents[openai]>=1.0.0`, `rank-bm25>=0.2.2`
- Node.js 24.x
- Ollama running with a loaded model
- Per-fixture: `npm install` in each `target_project/`
