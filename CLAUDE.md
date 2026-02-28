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
├── requirements.txt               # ollama, rich
├── CLAUDE.md
├── specs.md
├── README.md
│
├── src/
│   ├── common/
│   │   └── ollama_client.py       # Shared Ollama API wrapper
│   └── refactoring/
│       ├── simple_component/
│       │   ├── test_runner.py     # RefactoringTest + BenchmarkResult
│       │   └── validator.py
│       └── typed_emits_composable/
│           ├── test_runner.py
│           └── validator.py
│
├── scripts/
│   └── parse_vue_ast.js           # Node.js AST parser (@vue/compiler-sfc + Babel)
│
├── fixtures/
│   └── refactoring/
│       ├── simple-component/
│       │   ├── target_project/    # Complete Vue 3 project (npm install done)
│       │   ├── prompt.md
│       │   └── validation_spec.json
│       └── typed-emits-composable/
│           ├── target_project/    # Complete Vue 3 project (npm install done)
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

### Per-fixture layout ([src/refactoring/](src/refactoring/))

Each fixture has its own `test_runner.py` and `validator.py`. Duplication is intentional — fixture-specific logic (especially `validate_naming()`) diverges enough to make shared abstractions premature.

Each `test_runner.py` also exposes a module-level `format_run(result: BenchmarkResult) -> None` function that handles the per-run console output for that fixture. `run_test.py` calls it via the imported module — no display logic lives in `run_test.py`.

### [run_test.py](run_test.py) — CLI entry point

```
python run_test.py --model <model> [--fixture <name>] [--runs <n>]
```

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

1. Create `fixtures/refactoring/<fixture-name>/` with `prompt.md`, `validation_spec.json`, `target_project/`
2. Run `npm install` in `target_project/`
3. Create `src/refactoring/<fixture_name>/` with `__init__.py`, `test_runner.py`, `validator.py`
4. Register in [run_test.py](run_test.py) `_RUNNER_MAP`
5. Write tests first (TDD)

---

## Dependencies

- Python 3.12+, `ollama>=0.4.0`, `rich>=13.0.0`
- Node.js 24.x
- Ollama running with a loaded model
- Per-fixture: `npm install` in each `target_project/`
