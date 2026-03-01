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
│   │   └── veevalidate_zod_form/
│   │       ├── test_runner.py     # CreationTest + BenchmarkResult
│   │       └── validator.py
│   └── agent/
│       ├── common/
│       │   ├── tools.py           # make_tools() factory (read/write/list/compile)
│       │   └── agent_client.py    # run_agent() → AgentRunResult
│       └── ts_bugfix/
│           ├── test_runner.py     # AgentTest + AgentBenchmarkResult
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
│   │   └── veevalidate-zod-form/
│   │       ├── target_project/
│   │       ├── prompt.md
│   │       └── validation_spec.json
│   └── agent/
│       └── ts-bugfix/
│           ├── target_project/    # Vue 3 project with intentionally broken component
│           ├── prompt.md
│           └── validation_spec.json
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
- `iterations` (count of `run_compilation` calls) is an observational metric
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

---

## Adding a New Fixture

> **Naming convention**: fixture directories use kebab-case (`my-fixture`), Python modules use snake_case (`my_fixture`). The mapping is explicit in `_RUNNER_MAP`.

### Refactoring / Creation fixture
1. Create `fixtures/<category>/<fixture-name>/` with `prompt.md`, `validation_spec.json`, `target_project/`
2. Run `npm install` in `target_project/`
3. Create `src/<category>/<fixture_name>/` with `__init__.py`, `test_runner.py`, `validator.py`
4. Register in [run_test.py](run_test.py) `_RUNNER_MAP`
5. Write tests first (TDD)

### Agent fixture
1. Create `fixtures/agent/<fixture-name>/` with `prompt.md`, `validation_spec.json` (include `max_steps`), `target_project/`
2. Run `npm install` in `target_project/`; ensure `npm run type-check` is configured
3. Create `src/agent/<fixture_name>/` with `__init__.py`, `test_runner.py` (`AgentTest` + `AgentBenchmarkResult`), `validator.py`
4. Register in [run_test.py](run_test.py) `_RUNNER_MAP`
5. Write tests first (TDD)

---

## Dependencies

- Python 3.12+, `ollama>=0.4.0`, `rich>=13.0.0`, `smolagents[openai]>=1.0.0`
- Node.js 24.x
- Ollama running with a loaded model
- Per-fixture: `npm install` in each `target_project/`
