# LLM Benchmark Suite

Local benchmarking tool for testing LLM performance on Vue.js/TypeScript development tasks using Ollama.

## Overview

Benchmarks LLMs on real-world Vue.js tasks across three categories:
- **Refactoring** — add TypeScript type safety to existing Vue 3 components
- **Creation** — implement a complete component from scratch given a spec
- **Agent** — multi-turn tool-calling loop: the model reads files, writes fixes, and verifies compilation autonomously

Single-shot categories (refactoring/creation) validate the LLM response with TypeScript compiler (`vue-tsc`) and pattern checks, scoring on compilation success, pattern conformance, and naming conventions. The agent category additionally tracks steps used and compilation attempts.

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
npm install --prefix fixtures/creation/veevalidate-zod-form/target_project
npm install --prefix fixtures/agent/ts-bugfix/target_project
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
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --fixture veevalidate-zod-form
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --fixture ts-bugfix

# Change number of runs
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --runs 5
```

Results are saved as JSON to `results/` (gitignored):
```
results/{model}_{fixture}_{timestamp}.json
```

## Fixtures

### Agent

#### `ts-bugfix`
Fix TypeScript compilation errors in a Vue 3 component using a tool-calling agent loop. The model receives a broken component and must autonomously read the file, identify errors, write a fix, and verify compilation.

Intentional bugs: wrong prop type (`string` instead of `number`), missing `computed` import from Vue.

Expected output: correct `ButtonProps` interface, `defineProps<ButtonProps>()`, `computed` imported, `lang="ts"`.

Max score: **10.0/10** — scored on final compilation result, not on number of steps.
Additional metrics: steps used (out of `max_steps: 20`), number of compilation attempts.

### Refactoring

#### `simple-component`
Add TypeScript types to a basic Vue 3 component with three props (`title`, `count`, `items`).

Expected output: `HelloWorldProps` interface, `defineProps<HelloWorldProps>()`, `lang="ts"`.

Max score: **10.0/10**

#### `typed-emits-composable`
Add full TypeScript type safety to a component with props, typed emits with payloads, computed return type annotation, and type imports.

Expected output: `UserProfileProps` + `UserProfileEmits` interfaces, `defineEmits<UserProfileEmits>()`, `ComputedRef<string>` annotation, `import type { User }`.

Max score: **10.0/10** — harder prompt, more patterns required.

### Creation

#### `veevalidate-zod-form`
Implement a complete registration form from scratch using VeeValidate 4 + Zod schema validation. The model receives only a spec — no existing code to refactor.

Expected output: Zod schema (`z.object`) with 6 fields, `useForm` + `toTypedSchema`, `useField`/`defineField` bindings, template with all fields (text, email, password, radio, checkbox, textarea), error messages displayed.

Required fields: `username` (min 3), `email`, `password` (min 8), `role` (enum), `terms` (literal true), `bio` (optional).

Max score: **10.0/10**

## Scoring

Each run produces a `final_score` (0–10) weighted across three dimensions:

| Dimension     | Weight | What it checks |
|---------------|--------|----------------|
| Compilation   | 50%    | `vue-tsc --build` passes without errors |
| Pattern match | 40%    | Required patterns present in the component |
| Naming        | 10%    | Variables/interfaces follow fixture conventions |

Pattern checks vary by fixture category:

**Refactoring** — AST-based (Node.js `@vue/compiler-sfc` + Babel):
- TypeScript interface declarations
- Type annotations (`defineProps<T>`, `defineEmits<T>`, return types)
- Import statements (`import type`, module sources)
- `lang="ts"` on script tag

**Creation** — regex-based:
- `lang="ts"` on script tag
- `useForm(` call present
- `z.object(` and `toTypedSchema(` both present
- All required field names present in the component
- Error display (`errors.field` or `<ErrorMessage>`)

**Agent** — same pipeline as refactoring (AST-based), applied to the final state of the file after the agent loop completes. Additional metrics (not part of the score):

| Metric | Description |
|--------|-------------|
| `steps` | Total tool-calling turns used |
| `iterations` | Number of `run_compilation` calls |
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
│   ├── refactoring/
│   │   ├── simple_component/
│   │   │   ├── test_runner.py     # RefactoringTest orchestrator + BenchmarkResult
│   │   │   └── validator.py       # AST-based validation
│   │   └── typed_emits_composable/
│   │       ├── test_runner.py
│   │       └── validator.py       # validate_naming supports interface_suffixes list
│   ├── creation/
│   │   └── veevalidate_zod_form/
│   │       ├── test_runner.py     # CreationTest orchestrator + BenchmarkResult
│   │       └── validator.py       # Regex-based validation (no AST parser)
│   └── agent/
│       ├── common/
│       │   ├── tools.py           # make_tools() factory (read/write/list/compile)
│       │   └── agent_client.py    # run_agent() → AgentRunResult (smolagents wrapper)
│       └── ts_bugfix/
│           ├── test_runner.py     # AgentTest + AgentBenchmarkResult
│           └── validator.py       # AST-based validation (same pipeline as refactoring)
│
├── fixtures/
│   ├── refactoring/
│   │   ├── simple-component/
│   │   │   ├── prompt.md          # LLM prompt template ({{original_code}})
│   │   │   ├── validation_spec.json
│   │   │   └── target_project/    # Complete Vue 3 project (npm install here)
│   │   └── typed-emits-composable/
│   │       ├── prompt.md
│   │       ├── validation_spec.json
│   │       └── target_project/
│   ├── creation/
│   │   └── veevalidate-zod-form/
│   │       ├── prompt.md          # Full spec prompt (no {{original_code}})
│   │       ├── validation_spec.json
│   │       └── target_project/    # Vue 3 + vee-validate + zod (npm install here)
│   └── agent/
│       └── ts-bugfix/
│           ├── prompt.md          # Task prompt (no template substitution)
│           ├── validation_spec.json  # includes max_steps
│           └── target_project/    # Vue 3 project with broken component (npm install here)
│
├── scripts/
│   └── parse_vue_ast.js           # Node.js AST parser (@vue/compiler-sfc + Babel)
│
├── tests/                         # TDD test suite
│   ├── test_ollama_client.py
│   ├── test_validator.py
│   ├── test_refactoring_test.py
│   ├── test_typed_emits_validator.py
│   ├── test_run_test.py
│   ├── test_veevalidate_validator.py
│   ├── test_agent_tools.py
│   ├── test_agent_client.py
│   └── test_agent_test_runner.py
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

#### Refactoring fixture

1. Create `fixtures/refactoring/<fixture-name>/` with:
   - `prompt.md` — LLM prompt template using `{{original_code}}`
   - `validation_spec.json` — required patterns, naming conventions, scoring weights
   - `target_project/` — complete Vue 3 project (`npm install` before running)

2. Create `src/refactoring/<fixture_name>/` with:
   - `__init__.py`
   - `validator.py` — copy from an existing fixture and adjust `validate_naming()` as needed
   - `test_runner.py` — copy from an existing fixture, update the `validator` import

3. Register in `run_test.py`:
   ```python
   _RUNNER_MAP = {
       ...
       "new-fixture-name": "src.refactoring.new_fixture_name.test_runner",
   }
   ```

4. Write tests in `tests/test_<fixture_name>_validator.py`.

#### Agent fixture

1. Create `fixtures/agent/<fixture-name>/` with:
   - `prompt.md` — task description (no `{{original_code}}` placeholder)
   - `validation_spec.json` — required patterns, naming conventions, scoring weights, `max_steps`
   - `target_project/` — Vue 3 project with an intentionally broken component (`npm install` + verify `npm run type-check` reports errors)

2. Create `src/agent/<fixture_name>/` with:
   - `__init__.py`
   - `validator.py` — copy from `simple_component/validator.py` and adjust patterns
   - `test_runner.py` — use `AgentTest` class (copy from `ts_bugfix/test_runner.py`)

3. Register in `run_test.py`:
   ```python
   _RUNNER_MAP = {
       ...
       "new-fixture-name": "src.agent.new_fixture_name.test_runner",
   }
   ```

4. Write tests in `tests/test_agent_<fixture_name>.py`.

#### Creation fixture

1. Create `fixtures/creation/<fixture-name>/` with:
   - `prompt.md` — full spec prompt (no `{{original_code}}` placeholder)
   - `validation_spec.json` — required patterns, naming conventions, scoring weights
   - `target_project/` — Vue 3 project with dependencies pre-installed, empty target component

2. Create `src/creation/<fixture_name>/` with:
   - `__init__.py`
   - `validator.py` — implement regex-based `validate_ast_structure()` and `validate_naming()`
   - `test_runner.py` — use `CreationTest` class (copy from `veevalidate_zod_form/test_runner.py`)

3. Register in `run_test.py`:
   ```python
   _RUNNER_MAP = {
       ...
       "new-fixture-name": "src.creation.new_fixture_name.test_runner",
   }
   ```

4. Write tests in `tests/test_<fixture_name>_validator.py`.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
