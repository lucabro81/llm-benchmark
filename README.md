# LLM Benchmark Suite

Local benchmarking tool for testing LLM performance on Vue.js/TypeScript development tasks using Ollama.

## Overview

Benchmarks LLMs on real-world refactoring tasks by:
- Prompting the model to add TypeScript type safety to Vue 3 components
- Validating output with TypeScript compiler (`vue-tsc`) and AST structure checks
- Scoring on compilation success, pattern conformance, and naming conventions
- Collecting performance metrics (tokens/sec, duration)

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

# Per-fixture Node.js dependencies (vue-tsc, needed for compilation validation)
npm install --prefix fixtures/refactoring/simple-component/target_project
npm install --prefix fixtures/refactoring/typed-emits-composable/target_project
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

# Run all fixtures with a model (3 runs each)
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0

# Run a specific fixture
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --fixture simple-component

# Change number of runs
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --runs 5
```

Results are saved as JSON to `results/` (gitignored):
```
results/{model}_{fixture}_{timestamp}.json
```

## Fixtures

### `simple-component`
Add TypeScript types to a basic Vue 3 component with three props (`title`, `count`, `items`).

Expected output: `HelloWorldProps` interface, `defineProps<HelloWorldProps>()`, `lang="ts"`.

Max score: **10.0/10**

### `typed-emits-composable`
Add full TypeScript type safety to a component with props, typed emits with payloads, computed return type annotation, and type imports.

Expected output: `UserProfileProps` + `UserProfileEmits` interfaces, `defineEmits<UserProfileEmits>()`, `ComputedRef<string>` annotation, `import type { User }`.

Max score: **10.0/10** — harder prompt, more patterns required.

## Scoring

Each run produces a `final_score` (0–10) weighted across three dimensions:

| Dimension       | Weight | What it checks |
|----------------|--------|----------------|
| Compilation     | 50%    | `vue-tsc --noEmit` passes |
| Pattern match   | 40%    | AST: interfaces, type annotations, `lang="ts"` |
| Naming          | 10%    | Interface names follow fixture conventions |

Naming conventions are declared per fixture in `validation_spec.json` — each fixture can define its own accepted suffixes (e.g. `["Props"]` or `["Props", "Emits"]`).

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
│   └── refactoring/
│       ├── simple_component/
│       │   ├── test_runner.py     # RefactoringTest orchestrator + BenchmarkResult
│       │   └── validator.py       # validate_compilation, validate_ast_structure, validate_naming
│       └── typed_emits_composable/
│           ├── test_runner.py     # Same workflow, different validator import
│           └── validator.py       # validate_naming supports interface_suffixes list
│
├── fixtures/
│   └── refactoring/
│       ├── simple-component/
│       │   ├── prompt.md          # LLM prompt template ({{original_code}})
│       │   ├── validation_spec.json
│       │   └── target_project/    # Complete Vue 3 project (npm install here)
│       └── typed-emits-composable/
│           ├── prompt.md
│           ├── validation_spec.json
│           └── target_project/    # Complete Vue 3 project (npm install here)
│
├── scripts/
│   └── parse_vue_ast.js           # Node.js AST parser (@vue/compiler-sfc + Babel)
│
├── tests/                         # TDD test suite
│   ├── test_ollama_client.py
│   ├── test_validator.py
│   ├── test_refactoring_test.py
│   ├── test_typed_emits_validator.py
│   └── test_run_test.py
│
└── results/                       # Benchmark outputs (gitignored)
```

## Development

### Running Tests

```bash
source venv/bin/activate

# All tests (unit + integration)
pytest

# Unit tests only (no Ollama required)
pytest -m "not integration"

# Verbose
pytest -v
```

Integration tests (marked `@pytest.mark.integration`) require a live Ollama instance with the model loaded. They will fail on dev machines without the model — this is expected.

### Adding a New Fixture

1. Create `fixtures/refactoring/<fixture-name>/` with:
   - `prompt.md` — LLM prompt template using `{{original_code}}`
   - `validation_spec.json` — required patterns, naming conventions, scoring weights
   - `target_project/` — complete Vue 3 project (`npm install` before running)

2. Create `src/refactoring/<fixture_name>/` with:
   - `__init__.py`
   - `validator.py` — copy from an existing fixture and adjust `validate_naming()` as needed
   - `test_runner.py` — copy from an existing fixture, update the `validator` import

3. Register the fixture in `run_test.py`:
   ```python
   _RUNNER_MAP = {
       ...
       "new-fixture-name": "src.refactoring.new_fixture_name.test_runner",
   }
   ```

4. Write tests in `tests/test_<fixture_name>_validator.py`.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
