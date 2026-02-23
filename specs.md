# LLM Benchmark - Implementation Specs & Checklist

**Project**: Local LLM Benchmarking Tool
**Created**: 2026-02-01
**Last Updated**: 2026-02-23
**Status**: Phase 1 — COMPLETED ✅

---

## Implementation Phases

### Phase 1: Prompt-Only Baseline — ✅ COMPLETED

**Goal**: Validate workflow with simplest possible setup

**Approach**:
- Single prompt → LLM generates complete code → validate
- No tool-calling, no iterations
- LLM must produce correct code in one shot

**Success Criteria** (all met):
- ✅ Runs 10 consecutive tests without crashes
- ✅ Produces valid JSON results
- ✅ Metrics are sensible (tokens/sec, scores)
- ✅ CLI operational

**Components Delivered**:
- `src/common/ollama_client.py` — Ollama API wrapper
- ~~`gpu_monitor.py`~~ — **REMOVED** (superfluous on dedicated inference HW)
- `src/refactoring/simple_component/validator.py` — compilation + AST + naming
- `src/refactoring/simple_component/test_runner.py` — orchestrator
- `src/refactoring/typed_emits_composable/validator.py` — extended naming (interface_suffixes)
- `src/refactoring/typed_emits_composable/test_runner.py` — orchestrator (same interface)
- `run_test.py` — CLI entry point
- Fixtures: `simple-component`, `typed-emits-composable`

---

### Phase 2: Tool-Calling Agent (NEXT)

**Goal**: Reflect real-world agent usage patterns

**Approach**:
- Provide LLM with tools: `read_file`, `write_file`, `run_type_check`, `finish`
- Iterative loop (max 5-10 iterations)
- LLM can read errors, self-correct, validate incrementally

**New Metrics to Track**:
- `tool_calls_count`: Total tool calls per task
- `iterations_to_success`: How many cycles to complete
- `tools_used`: Sequence of tools used (for pattern analysis)
- `self_corrected`: Boolean, did LLM read compile errors and fix?

**Implementation Changes**:
- Update `ollama_client.py` for function calling (Ollama 0.3+ supports this)
- Add `test_runner_agent.py` per fixture with agent loop
- Update fixtures with examples of expected tool sequences
- Add efficiency scoring (penalize excessive iterations)

**New Data Structures**:
```python
@dataclass
class ToolCall:
    name: str
    parameters: dict

@dataclass
class AgentBenchmarkResult(BenchmarkResult):
    tool_calls_count: int
    iterations_to_success: int
    tools_used: List[str]
    self_corrected: bool
    efficiency_score: float
```

---

## Implementation Roadmap

### Phase 1: Project Setup — ✅ COMPLETED
- [x] Create project structure (directories)
- [x] Setup Python virtual environment (alias: `llmbench`)
- [x] Install dependencies (requirements.txt)
- [x] Verify system requirements (TypeScript, Ollama)
- [x] Create .gitignore
- [x] Create README.md with usage documentation

### Phase 2: Core Components

#### 2.1 Ollama Client (`src/common/ollama_client.py`) — ✅ COMPLETED
- [x] Create `ChatResult` dataclass
- [x] Implement `chat()` function
- [x] Add error handling (ModelNotFoundError, TimeoutError, OllamaConnectionError)
- [x] Parse response metadata (tokens, duration from eval_count / eval_duration nanoseconds)
- [x] Add timeout support
- [x] Implement `get_ollama_base_url()` (reads OLLAMA_BASE_URL env var)
- [x] Unit tests — 13 tests passing

#### 2.2 GPU Monitor — ✅ REMOVED
> **Decision**: GPU monitoring was implemented then removed. On dedicated inference hardware (NVIDIA GB10 Blackwell), the GPU is always near 100% utilization — the metric carries no signal. Removed to simplify the codebase.

#### 2.3 Validator (`src/refactoring/<fixture>/validator.py`) — ✅ COMPLETED
- [x] Create `CompilationResult` dataclass (with `duration_sec`)
- [x] Create `ASTResult` dataclass
- [x] Create `NamingResult` dataclass
- [x] Implement `validate_compilation()` (runs `npm run type-check` in target_project)
- [x] Implement `validate_ast_structure()` (calls Node.js parser, raises on failure)
- [x] Implement `validate_naming()` with `interface_suffixes` (list) + legacy `props_interface_suffix` support
- [x] Create `scripts/parse_vue_ast.js` (@vue/compiler-sfc + Babel)
- [x] Install Node.js deps in each fixture's target_project
- [x] Unit tests — 17 tests (simple_component) + 8 tests (typed_emits) passing

#### 2.4 Test Runner (`src/refactoring/<fixture>/test_runner.py`) — ✅ COMPLETED
- [x] Create `BenchmarkResult` dataclass (replaces `TestResult`; no GPU fields)
- [x] Implement `RefactoringTest` class
- [x] Fixture loading (prompt.md, validation_spec.json, target_project/)
- [x] Prompt template rendering (`{{original_code}}` substitution)
- [x] Ollama client integration
- [x] Write LLM output to target file, restore original in finally block
- [x] Compilation validation
- [x] AST pattern validation (try/except → degraded result on crash)
- [x] Naming validation (try/except → degraded result on crash)
- [x] Weighted composite scoring from validation_spec.json
- [x] `_extract_vue_code()` — strips markdown fences from LLM response
- [x] Unit tests — 10 tests (simple_component) + 3 exception handling tests passing

### Phase 3: Fixtures — ✅ COMPLETED

#### 3.1 `simple-component`
- [x] Create `fixtures/refactoring/simple-component/` directory
- [x] Create `target_project/` (Vue 3 + TypeScript)
- [x] Write `package.json`, `tsconfig.json`, `vite.config.ts`
- [x] Write `src/components/HelloWorld.vue` (untyped initial state)
- [x] Write `prompt.md` (template with `{{original_code}}`)
- [x] Write `validation_spec.json` (HelloWorldProps, Props suffix)
- [x] Run `npm install` in target_project
- [x] Validated: `npm run type-check` passes on original code

#### 3.2 `typed-emits-composable`
- [x] Create `fixtures/refactoring/typed-emits-composable/`
- [x] Create `target_project/` (Vue 3 + TypeScript)
- [x] Write `src/components/UserProfile.vue` (untyped)
- [x] Write `src/types/user.ts` (User interface)
- [x] Write `prompt.md` — specifies object-type syntax for emit interfaces (NOT call signatures)
- [x] Write `validation_spec.json` (UserProfileProps, UserProfileEmits, interface_suffixes)
- [x] Run `npm install` in target_project (fresh install, no cp -r to preserve symlinks)
- [x] Validated: 10 runs, ~70-100% compile success rate depending on model output

### Phase 4: Runner Script — ✅ COMPLETED

#### 4.1 CLI Entry Point (`run_test.py`)
- [x] `parse_arguments()` — `--model` (required), `--fixture` (optional), `--runs` (default 3)
- [x] `discover_fixtures()` — scans fixtures/refactoring/ for dirs with validation_spec.json
- [x] `_RUNNER_MAP` + `_get_runner_class()` — dynamic import per fixture
- [x] `run_fixture()` — loop with `── Run X/N ──` counter (no progress bar)
- [x] `show_run_summary()` — per-run detail with scoring breakdown, AST checks, naming, errors
- [x] `show_fixture_summary()` — aggregate stats per fixture
- [x] `show_overall_summary()` — cross-fixture aggregate (only when >1 fixture)
- [x] `save_results()` — JSON per fixture: `{model}_{fixture}_{timestamp}.json`
- [x] Error handling: fixture load failure → skip + continue; exit code 1 if any failure
- [x] Unit tests — 9 tests passing (discover_fixtures, summary stats, JSON serialization)

### Phase 5: Validation & Testing — ✅ COMPLETED (on GPU machine)

- [x] Verify Ollama model available
- [x] Validate fixture target_projects compile with vue-tsc
- [x] Run complete benchmark (10 iterations)
- [x] Verify JSON output format
- [x] Validate TypeScript detection works
- [x] Confirm AST scoring accuracy
- [x] Verify performance metrics (tok/s)

### Phase 6: Documentation — ✅ COMPLETED
- [x] README.md — usage, architecture, both fixtures, "Adding a New Fixture" guide
- [x] CLAUDE.md — updated to v2.0 reflecting current state
- [x] specs.md — this file, updated to current state

---

## Implementation Details

### Directory Structure (actual)
```
llm-benchmark/
├── venv/
├── requirements.txt
├── .gitignore
├── CLAUDE.md
├── specs.md
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   └── ollama_client.py
│   └── refactoring/
│       ├── __init__.py
│       ├── simple_component/
│       │   ├── __init__.py
│       │   ├── test_runner.py
│       │   └── validator.py
│       └── typed_emits_composable/
│           ├── __init__.py
│           ├── test_runner.py
│           └── validator.py
│
├── scripts/
│   └── parse_vue_ast.js
│
├── fixtures/
│   └── refactoring/
│       ├── simple-component/
│       │   ├── target_project/
│       │   ├── prompt.md
│       │   └── validation_spec.json
│       └── typed-emits-composable/
│           ├── target_project/
│           ├── prompt.md
│           └── validation_spec.json
│
├── tests/
│   ├── test_ollama_client.py
│   ├── test_validator.py
│   ├── test_refactoring_test.py
│   ├── test_typed_emits_validator.py
│   └── test_run_test.py
│
├── results/
│   └── .gitkeep
│
└── run_test.py
```

### Dependencies
```
ollama>=0.4.0
rich>=13.0.0
```

### CLI Usage
```bash
# Run all fixtures, 3 runs each
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0

# Run specific fixture, 10 runs
python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --fixture typed-emits-composable --runs 10
```

---

## Data Structures

### ChatResult
```python
@dataclass
class ChatResult:
    response_text: str
    duration_sec: float
    tokens_generated: int
    tokens_per_sec: float
    success: bool
    error: Optional[str] = None
```

### CompilationResult
```python
@dataclass
class CompilationResult:
    success: bool
    errors: List[str]
    warnings: List[str]
    duration_sec: float
```

### ASTResult
```python
@dataclass
class ASTResult:
    has_interfaces: bool
    has_type_annotations: bool
    has_imports: bool
    missing: List[str]
    score: float  # 0.0-10.0
```

### NamingResult
```python
@dataclass
class NamingResult:
    follows_conventions: bool
    violations: List[str]
    score: float  # 0.0-1.0
```

### BenchmarkResult
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
    pattern_score: float          # 0-10 from AST validation
    ast_missing: List[str]
    naming_score: float           # 0-10 (naming_result.score * 10)
    naming_violations: List[str]
    final_score: float            # 0-10 weighted composite
    scoring_weights: dict         # {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1}
    tokens_per_sec: float
    duration_sec: float
    output_code: str
    errors: List[str]             # validation errors (AST crash, naming crash, etc.)
```

---

## Testing Strategy

### Unit Tests (57 passing, 1 integration expected to fail without local model)
- `test_ollama_client.py` — mock Ollama API, error mapping, token parsing
- `test_validator.py` — AST validation, compilation, naming (simple_component)
- `test_refactoring_test.py` — scoring logic, file restoration, exception handling
- `test_typed_emits_validator.py` — interface_suffixes, exception handling (typed_emits runner)
- `test_run_test.py` — discover_fixtures, summary stats, JSON serialization

### Integration Tests (run on GPU machine only)
- `test_ollama_client.py::TestChatIntegration::test_real_ollama_call` — real Ollama call
- marked `@pytest.mark.integration`

### TDD Discipline
- Tests written before implementation (Red → Green → Refactor)
- Exception handling tests: validated by running 10 benchmark iterations and observing graceful degradation on AST crashes

---

## Success Criteria — ✅ ALL MET

- [x] All unit tests pass (57/57; 1 integration skipped on dev machine)
- [x] Both fixture target_projects compile with vue-tsc
- [x] Integration test completes 10 runs without process crash
- [x] Compilation validation detects TypeScript errors correctly
- [x] Pattern validation scores perfect output as 10/10
- [x] Weighted scoring correctly combines compilation + pattern + naming scores
- [x] Results JSON is well-formed with all expected fields
- [x] Performance ~31 tok/s on GB10 Blackwell (7B Q8 model)

---

## Known Issues / Limitations

### Current Limitations
- Two test scenarios only (TypeScript props refactoring, typed emits/composable)
- Single file per fixture (no multi-file refactoring)
- Basic pattern matching (presence check, not usage correctness)
- No statistical aggregation (raw JSON only)
- No report generation
- No multi-model comparison UI (run manually with different --model)
- AST parser does not support TypeScript call signature syntax for emit interfaces

### Future Enhancements (Post-Phase 1)
- Multiple test scenarios (Vue 2→3 migration, Nuxt 3, design system)
- Tool-calling agent mode (Phase 2)
- Markdown/CSV report generation
- Vitest functional testing
- Advanced pattern tracking (composable usage, reactivity API)
- Architecture detection (MoE vs Dense)
- Statistical aggregation across runs

---

## Notes

- Per-fixture duplication in `src/refactoring/` is deliberate — better 10% critical difference in the right place than premature abstraction
- Object-type syntax for emit interfaces is required in prompts (`'event': [payload]`, not `('event': [payload]): void`)
- Restore target file always happens in `finally` block — safe to interrupt runs
- Commit after each meaningful change; use TDD cycle for new features

---

**Last Updated**: 2026-02-23
**Current Phase**: Phase 1 COMPLETED
**Next Milestone**: Phase 2 — Tool-Calling Agent
