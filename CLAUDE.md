# LLM Benchmark Suite - Implementation Plan v2.0

**Project**: Local LLM Benchmarking Tool for Vue.js/Nuxt/TypeScript Development
**Date**: 2026-02-23
**Phase**: MVP Phase 1 — COMPLETED

---

## Implementation Phases

### Phase 1: Prompt-Only Baseline — ✅ COMPLETED
**Goal**: Validate workflow with simplest possible setup

**Approach**:
- Single prompt → LLM generates complete code → validate
- No tool-calling, no iterations
- LLM must produce correct code in one shot

**Outcome**:
- Infrastructure proven: 2 fixtures, dual validation, comprehensive metrics, JSON output
- Baseline metrics established on dedicated NVIDIA inference hardware
- 57 unit tests passing (1 integration test requires GPU machine + model)
- GPU monitoring removed — on dedicated inference hardware the GPU is always at 100%, making the metric meaningless

**Design decisions made during Phase 1**:
- `gpu_monitor.py` removed — superfluous metric on dedicated inference HW
- `src/` organized per-fixture (`src/refactoring/<fixture>/`) — deliberate duplication over premature abstraction
- `validate_naming()` added with `interface_suffixes` (list) support
- Exception handling in test runner: AST crash → degraded `BenchmarkResult`, not process crash
- Progress bar replaced with `── Run X/N ──` run counter for cleaner terminal output

**Success Criteria** (all met):
- ✅ Runs 10 consecutive tests without crashes
- ✅ Produces valid JSON results
- ✅ Metrics are sensible (tokens/sec, scores)
- ✅ Compilation succeeds with vue-tsc in target project
- ✅ Pattern validation scores perfect output as 10/10
- ✅ CLI operational (`--model`, `--fixture`, `--runs`)

### Phase 2: Tool-Calling Agent (NEXT)
**Goal**: Reflect real-world agent usage patterns

**Approach**:
- Provide LLM with tools: `read_file`, `write_file`, `run_type_check`, `finish`
- Iterative loop (max 5-10 iterations)
- LLM can read errors, self-correct, validate incrementally

**Rationale**:
- Real coding agents (Claude Code, Cursor, Aider) work this way
- Tests both code generation AND tool usage skill
- Weaker models may compensate with better iteration strategy

**New Metrics to Track**:
- `tool_calls_count`: Total tool calls per task
- `iterations_to_success`: How many cycles to complete
- `tools_used`: Sequence of tools used (for pattern analysis)
- `self_corrected`: Boolean, did LLM read compile errors and fix?

**Implementation**:
- Update `ollama_client.py` for function calling (Ollama 0.3+ supports this)
- Add per-fixture `test_runner_agent.py` with agent loop
- Update fixtures with examples of expected tool sequences
- Add efficiency scoring (penalize excessive iterations)

---

## Development Workflow & Rules of Engagement

### Fundamental Principle
Our workflow is dynamic: **Initial Plan ➔ Step-by-step Execution with Revision possibility for each step ➔ Final Approval in the CLI**. This ensures that the plan can adapt to new information or requirement changes that emerge during development.

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
- Tests should be written based on the expected behavior and requirements
- Follow the TDD cycle: Red (write failing test) → Green (implement minimal code) → Refactor
- Tests define the contract and expected outcomes before implementation begins

### Development Environment
- Python virtual environment managed with `venv`
- Activate environment using the alias: `llmbench`
- All development work should be done within the activated virtual environment

---

## Objective

Create a tool to benchmark LLMs locally using Ollama in controlled Vue.js project environments. The tool provides test scenarios (Vue 2→3 migration, Nuxt projects, design system integration, etc.), executes LLM tasks, validates compilation and pattern conformance, and collects comprehensive metrics.

---

## Scope MVP

### What's IN (Phase 1 — delivered)
- **Two test fixtures**: `simple-component` (props typing) and `typed-emits-composable` (props + emits + computed)
- **Self-contained fixtures**: Each fixture includes a complete Vue project with dependencies
- **Dual validation**: TypeScript compilation (vue-tsc) + AST pattern conformance
- **Per-fixture src layout**: Each fixture has its own `test_runner.py` and `validator.py` under `src/refactoring/<fixture>/`; only the Ollama client lives in `src/common/`
- **Comprehensive metrics**: Compilation success, pattern score, naming score, scoring breakdown, tokens/sec, duration
- **In-place execution**: LLM modifies files directly in fixture's target project
- **Raw JSON output**: Structured results for future aggregation (one file per fixture per run)
- **CLI runner**: `--model` (required), `--fixture` (optional, runs all if omitted), `--runs` (default 3)
- **Graceful degradation**: AST/naming validation exceptions produce score=0 result, never crash the run loop

### What's OUT (Future Phases)
- Vue 2→3 migration, Nuxt projects, design system integration scenarios
- Report generation (Markdown/CSV)
- Data aggregation and statistics (mean, stddev across runs)
- Vitest functional testing (run code in browser)
- Architecture-aware comparisons (MoE vs Dense)
- Advanced pattern matching (composable usage tracking, component composition)
- Multi-file refactoring support

---

## Project Structure

```
~/Projects/llm-benchmark/
├── venv/                          # Python virtual environment
├── requirements.txt               # Python dependencies (ollama, rich)
├── .gitignore
├── CLAUDE.md                      # This file — project reference for Claude
├── specs.md                       # Implementation checklist
├── README.md                      # User-facing documentation
│
├── src/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   └── ollama_client.py       # Shared Ollama API wrapper
│   └── refactoring/
│       ├── __init__.py
│       ├── simple_component/
│       │   ├── __init__.py
│       │   ├── test_runner.py     # RefactoringTest + BenchmarkResult
│       │   └── validator.py       # validate_compilation, validate_ast_structure, validate_naming
│       └── typed_emits_composable/
│           ├── __init__.py
│           ├── test_runner.py     # same interface as simple_component
│           └── validator.py       # validate_naming extended with interface_suffixes
│
├── scripts/
│   └── parse_vue_ast.js           # Node.js AST parser (@vue/compiler-sfc + Babel)
│
├── fixtures/
│   └── refactoring/
│       ├── simple-component/
│       │   ├── target_project/    # Complete Vue 3 project (npm install done)
│       │   │   ├── package.json
│       │   │   ├── tsconfig.json
│       │   │   ├── vite.config.ts
│       │   │   └── src/components/HelloWorld.vue
│       │   ├── prompt.md
│       │   └── validation_spec.json
│       └── typed-emits-composable/
│           ├── target_project/    # Complete Vue 3 project (npm install done)
│           │   ├── package.json
│           │   ├── tsconfig.json
│           │   ├── vite.config.ts
│           │   └── src/
│           │       ├── components/UserProfile.vue
│           │       └── types/user.ts
│           ├── prompt.md
│           └── validation_spec.json
│
├── tests/
│   ├── test_ollama_client.py
│   ├── test_validator.py          # tests for simple_component validator
│   ├── test_refactoring_test.py   # tests for simple_component test_runner
│   ├── test_typed_emits_validator.py  # tests for typed_emits validator + runner
│   └── test_run_test.py           # tests for CLI runner + discover_fixtures
│
├── results/                       # gitignored, created at runtime
│   └── .gitkeep
│
└── run_test.py                    # CLI entry point
```

---

## Component Specifications

### 1. `src/common/ollama_client.py`

**Purpose**: Shared Ollama API wrapper with error handling and metrics extraction

**Key Functions**:
```python
def chat(model: str, prompt: str, timeout: int = 30) -> ChatResult:
    """
    Call Ollama chat API and return structured result

    Returns:
        ChatResult dataclass with:
        - response_text: str
        - duration_sec: float
        - tokens_generated: int
        - tokens_per_sec: float
        - success: bool
        - error: Optional[str]
    """
```

**Custom Exceptions**:
- `ModelNotFoundError` — model not in Ollama
- `OllamaConnectionError` — cannot reach Ollama API
- `TimeoutError` — request exceeded timeout

**Implementation Notes**:
- Uses `ollama.chat()` from Python SDK
- Reads `OLLAMA_BASE_URL` env var for non-default hosts
- Parses `eval_duration` (nanoseconds) and `eval_count` (tokens) from response metadata

---

### 2. `src/refactoring/<fixture>/validator.py`

**Purpose**: Dual validation — TypeScript compilation + AST pattern conformance + naming conventions

One copy per fixture. `simple_component/validator.py` and `typed_emits_composable/validator.py` are identical except for `validate_naming()`, which in the latter supports `interface_suffixes` (list).

**Key Functions**:
```python
def validate_compilation(target_project: Path) -> CompilationResult:
    """Run npm run type-check (vue-tsc) in target_project directory."""

def validate_ast_structure(code: str, expected_structures: dict) -> ASTResult:
    """
    Parse Vue SFC via Node.js (parse_vue_ast.js) and check for patterns.
    Raises Exception if parser returns non-zero exit code.
    Raises FileNotFoundError if Node.js or script not found.
    """

def validate_naming(code: str, conventions: dict) -> NamingResult:
    """
    Check interface naming conventions via regex.
    Supports:
      - interface_suffixes: ["Props", "Emits"]  ← list, takes precedence
      - props_interface_suffix: "Props"          ← legacy string, backward compat
    """
```

**Validation Architecture**:
```
LLM Output
    ↓
[1] TypeScript Compilation (vue-tsc via npm run type-check)
    ↓
[2] AST Pattern Matching (Node.js: @vue/compiler-sfc + Babel)
    ↓
[3] Naming Convention Check (Python regex on interface declarations)
    ↓
Composite Score
```

**Scoring Model** (from `validation_spec.json`):
```python
final_score = (
    (1.0 if compiles else 0.0) * weights["compilation"] +   # 50%
    (ast_result.score / 10.0) * weights["pattern_match"] +  # 40%
    naming_result.score * weights["naming"]                  # 10%
) * 10  # Scale to 0-10
```

**AST Parser Notes** (`scripts/parse_vue_ast.js`):
- Uses `compileScript` from `@vue/compiler-sfc` to extract Babel AST from `<script setup>`
- Call signature syntax (e.g. `('event': [payload]): void`) is NOT supported — use object-type syntax (`'event': [payload]`) for emit interfaces
- Checks: TSInterfaceDeclaration, type parameters in variable declarations, ImportDeclaration

---

### 3. `src/refactoring/<fixture>/test_runner.py`

**Purpose**: Orchestrate a single fixture's refactoring test execution

**Key Class**:
```python
class RefactoringTest:
    def __init__(self, model: str, fixture_path: Path):
        # Loads: prompt.md, validation_spec.json, original target file

    def run(self, run_number: int = 1) -> BenchmarkResult:
        """
        Steps:
        1. Restore original file
        2. Render prompt ({{original_code}} substitution)
        3. Call LLM via ollama_client.chat()
        4. Extract Vue code from response (strip markdown fences)
        5. Write output to target file
        6. validate_compilation() — always robust, returns CompilationResult
        7. validate_ast_structure() — wrapped in try/except → score=0 on crash
        8. validate_naming() — wrapped in try/except → score=0 on crash
        9. Calculate composite score
        10. Restore original file (finally block)
        11. Return BenchmarkResult
        """
```

**BenchmarkResult dataclass**:
```python
@dataclass
class BenchmarkResult:
    model: str
    fixture: str
    timestamp: str
    run_number: int
    compiles: bool
    compilation_errors: List[str]
    compilation_warnings: List[str]
    pattern_score: float         # 0-10 from AST validation
    ast_missing: List[str]       # which AST checks failed
    naming_score: float          # 0-10 (naming_result.score * 10)
    naming_violations: List[str]
    final_score: float           # 0-10 weighted composite
    scoring_weights: dict        # from validation_spec.json
    tokens_per_sec: float
    duration_sec: float
    output_code: str
    errors: List[str]            # validation errors (AST crash, naming crash, etc.)
```

**Error Handling**:
- `ModelNotFoundError`, `OllamaConnectionError` → propagate (fail fast)
- `validate_ast_structure()` raises → catch, append to `errors`, score=0
- `validate_naming()` raises → catch, append to `errors`, score=0
- File restoration always happens in `finally` block

---

### 4. `run_test.py`

**Purpose**: CLI entry point for running benchmarks

**CLI**:
```
python run_test.py --model <model> [--fixture <name>] [--runs <n>]

  --model    required  Ollama model name (e.g. qwen2.5-coder:7b-instruct-q8_0)
  --fixture  optional  Fixture name under fixtures/refactoring/ (runs ALL if omitted)
  --runs     optional  Number of runs per fixture (default: 3)
```

**Key Functions**:
```python
def discover_fixtures(base_dir: Path) -> List[Path]:
    """Scan fixtures/refactoring/ for dirs containing validation_spec.json, sorted."""

_RUNNER_MAP = {
    "simple-component": "src.refactoring.simple_component.test_runner",
    "typed-emits-composable": "src.refactoring.typed_emits_composable.test_runner",
}
# Adding a new fixture requires: (1) create files, (2) register here

def run_fixture(model, fixture_path, runs, runner_class) -> Optional[List[BenchmarkResult]]:
    """Run all runs for one fixture. Prints '── Run X/N ──' before each run."""
```

**Console output per run**:
```
── Run 1/10 ──
✓ Compile | ✓ Score   10.0/10  31.3 tok/s  7.5s
   Scoring:  compile 5.0pt (50%) + pattern 4.0pt (40%) + naming 1.0pt (10%)
   AST:      interfaces type_annotations script_lang  (score 10.0/10)
   Naming:   ✓ conventions  (score 10.0/10)
──────────
```

**JSON output**: one file per fixture per benchmark session:
```
results/{model}_{fixture}_{timestamp}.json
```

---

## Fixture Specifications

### `simple-component`

**Task**: Add TypeScript types to Vue 3 props (no emits, no imports)

**Target file**: `src/components/HelloWorld.vue`

**Expected output** (reference):
```vue
<script setup lang="ts">
interface HelloWorldProps {
  title: string
  count: number
  items: string[]
}
const props = defineProps<HelloWorldProps>()
const doubled = computed(() => props.count * 2)
</script>
```

**Scoring breakdown** (perfect output = 10.0/10):
- Compilation 50%: compiles with vue-tsc = 5.0pt
- Pattern 40%: interfaces ✓ + type_annotations ✓ + script_lang ✓ = 4.0pt
- Naming 10%: PascalCase + "Props" suffix = 1.0pt

**`validation_spec.json`**:
```json
{
  "target_file": "src/components/HelloWorld.vue",
  "required_patterns": {
    "interfaces": ["HelloWorldProps"],
    "type_annotations": ["HelloWorldProps"],
    "script_lang": "ts",
    "imports": []
  },
  "naming_conventions": {
    "interfaces": "PascalCase",
    "props_interface_suffix": "Props"
  },
  "scoring": { "compilation": 0.5, "pattern_match": 0.4, "naming": 0.1 }
}
```

---

### `typed-emits-composable`

**Task**: Add full TypeScript types — props + emits with payloads + computed return type + type imports

**Target file**: `src/components/UserProfile.vue`

**Expected output** (reference):
```vue
<script setup lang="ts">
import type { User } from '@/types/user'
import { computed, ComputedRef } from 'vue'

interface UserProfileProps {
  user: User
  editable: boolean
}

interface UserProfileEmits {
  'update:user': [user: User]
  'delete': [id: number]
}

const props = defineProps<UserProfileProps>()
const emit = defineEmits<UserProfileEmits>()

const displayName: ComputedRef<string> = computed(() => {
  return props.user?.name || 'Unknown User'
})
</script>
```

**Important**: emit interfaces must use **object-type syntax** (`'event': [payload]`), NOT call signatures (`('event': [payload]): void`). The latter is valid TypeScript but not supported by `@vue/compiler-sfc`'s `compileScript` + Babel parser.

**Scoring breakdown** (perfect output = 10.0/10):
- Compilation 50%: compiles with vue-tsc = 5.0pt
- Pattern 40%: interfaces ✓ + type_annotations ✓ + script_lang ✓ = 4.0pt
- Naming 10%: PascalCase + Props/Emits suffix = 1.0pt

**`validation_spec.json`**:
```json
{
  "target_file": "src/components/UserProfile.vue",
  "required_patterns": {
    "interfaces": ["UserProfileProps", "UserProfileEmits"],
    "type_annotations": ["UserProfileProps", "UserProfileEmits", "ComputedRef"],
    "script_lang": "ts",
    "imports": ["@/types/user", "vue"]
  },
  "naming_conventions": {
    "interfaces": "PascalCase",
    "interface_suffixes": ["Props", "Emits"]
  },
  "scoring": { "compilation": 0.5, "pattern_match": 0.4, "naming": 0.1 }
}
```

---

## Adding a New Fixture

1. Create `fixtures/refactoring/<fixture-name>/` with `prompt.md`, `validation_spec.json`, `target_project/`
2. Run `npm install` in `target_project/`
3. Create `src/refactoring/<fixture_name>/` with `__init__.py`, `test_runner.py`, `validator.py`
4. Register in `run_test.py` `_RUNNER_MAP`:
   ```python
   "fixture-name": "src.refactoring.fixture_name.test_runner",
   ```
5. Write tests in `tests/test_<fixture_name>_validator.py` (TDD)

---

## Dependencies

### `requirements.txt`
```
ollama>=0.4.0
rich>=13.0.0
```

### System Requirements
- Python 3.12+
- Node.js 24.x (for `parse_vue_ast.js` + `vue-tsc`)
- Per-fixture: `npm install` in each `target_project/` (installs vue-tsc, @vue/compiler-sfc)
- Ollama running with a loaded model
- NVIDIA GPU (recommended for inference speed; CPU works but is slow)

---

## Validation Checklist (Pre-Benchmark)

```bash
# 1. Python environment
source venv/bin/activate
python -c "import ollama, rich; print('OK')"

# 2. Node.js
node --version  # 24.x

# 3. Fixture dependencies
cd fixtures/refactoring/simple-component/target_project && npm run type-check
cd fixtures/refactoring/typed-emits-composable/target_project && npm run type-check

# 4. Ollama model
ollama list | grep qwen2.5-coder

# 5. Unit tests
pytest tests/ -v  # 57 passed, 1 failed (integration — expected without local model)
```

---

## Expected Output Format

### Console
```
╔════════════════════════════════════════════╗
║  LLM Benchmark - Phase 1 (Prompt-Only)     ║
╚════════════════════════════════════════════╝

Model:    qwen2.5-coder:7b-instruct-q8_0
Fixtures: typed-emits-composable
Runs:     3 per fixture

── Run 1/3 ──
✓ Compile | ✓ Score   10.0/10  31.3 tok/s  7.5s
   Scoring:  compile 5.0pt (50%) + pattern 4.0pt (40%) + naming 1.0pt (10%)
   AST:      interfaces type_annotations script_lang  (score 10.0/10)
   Naming:   ✓ conventions  (score 10.0/10)
──────────

Summary: typed-emits-composable
  Avg Final Score:   10.00/10
  Avg Pattern Score: 10.00/10
  Avg Naming Score:  10.00/10
  Avg Speed:         31.3 tok/s
  Avg Duration:      7.5s
  Compile Success:   100% (3/3 runs)
```

### JSON Result Structure
```json
[
  {
    "model": "qwen2.5-coder:7b-instruct-q8_0",
    "fixture": "typed-emits-composable",
    "timestamp": "2026-02-23T10:08:32.411345",
    "run_number": 1,
    "compiles": true,
    "compilation_errors": [],
    "compilation_warnings": [],
    "pattern_score": 10.0,
    "ast_missing": [],
    "naming_score": 10.0,
    "naming_violations": [],
    "final_score": 10.0,
    "scoring_weights": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
    "tokens_per_sec": 31.3,
    "duration_sec": 7.5,
    "output_code": "<script setup lang=\"ts\">...",
    "errors": []
  }
]
```

---

## Known Limitations (Phase 1)

1. **Two test scenarios only**: TypeScript props refactoring + typed emits/composable; no Vue 2→3 migration, Nuxt, or design system scenarios
2. **No aggregation**: Raw JSON only, no mean/stddev across runs
3. **Basic pattern matching**: Only checks for presence of patterns, not semantic correctness
4. **No Vitest**: Functional testing (running in browser) postponed
5. **No multi-model comparison UI**: Run script multiple times manually with different `--model`
6. **No architecture detection**: MoE vs Dense distinction not tracked
7. **Single file per fixture**: LLM modifies one file at a time
8. **AST parser limitations**: `@vue/compiler-sfc` + Babel does not support TypeScript call signature syntax in emit interfaces — prompts must specify object-type syntax

---

## Next Steps (Phase 2+)

1. **Phase 2 — Tool-Calling Agent**:
   - `read_file`, `write_file`, `run_type_check`, `finish` tools
   - Iterative loop (max 5-10 iterations)
   - New metrics: `tool_calls_count`, `iterations_to_success`, `self_corrected`
2. Add more scenarios: Vue 2→3 migration, Nuxt 3, design system integration
3. Statistical aggregation (mean, stddev across runs)
4. Markdown/CSV report generation
5. Vitest functional validation
6. Model architecture detection (MoE vs Dense)
7. Advanced pattern tracking (composable usage correctness, reactivity API)

---

## Notes

- **Per-fixture duplication is intentional**: `test_runner.py` and `validator.py` are ~90% identical between fixtures; the 10% difference in `validate_naming()` is fixture-specific and critical. Abstraction deferred until patterns stabilize.
- Keep temp files on validation errors for manual inspection
- If AST validation is too noisy, simplify checks in `validation_spec.json`
- Expect ~31 tok/s on GB10 Blackwell for 7B Q8 model (~7.5s per run)

---

**Document Version**: 2.0
**Last Updated**: 2026-02-23
**Status**: Phase 1 COMPLETED — Phase 2 (Tool-Calling) NEXT
