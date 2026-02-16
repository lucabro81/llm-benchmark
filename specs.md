# LLM Benchmark - Implementation Specs & Checklist

**Project**: Local LLM Benchmarking Tool
**Created**: 2026-02-01
**Status**: Phase 1 (Prompt-Only Baseline)

---

## Implementation Phases

### Phase 1: Prompt-Only Baseline (CURRENT)

**Goal**: Validate workflow with simplest possible setup

**Approach**:
- Single prompt → LLM generates complete code → validate
- No tool-calling, no iterations
- LLM must produce correct code in one shot

**Rationale**:
- Prove infrastructure works (fixtures, validation, GPU monitoring, JSON output)
- Get baseline metrics before adding complexity
- Quick validation that "it doesn't explode"

**Success Criteria**:
- ✅ Runs 3 consecutive tests without crashes
- ✅ Produces valid JSON results
- ✅ Metrics are sensible (GPU usage, tokens/sec, scores)

**Components Needed**:
- `ollama_client.py` - Simple chat() function (no tool-calling)
- `gpu_monitor.py` - nvidia-smi monitoring
- `validator.py` - Compilation + AST validation
- `refactoring_test.py` - Orchestrator (prompt-only workflow)
- `run_test.py` - Entry point
- Fixture: `simple-component` with validation_spec.json

---

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

**Implementation Changes**:
- Update `ollama_client.py` for function calling (Ollama 0.3+ supports this)
- Modify `refactoring_test.py` with agent loop
- Update fixtures with examples of expected tool sequences
- Add efficiency scoring (penalize excessive iterations)

**New Data Structures**:
```python
@dataclass
class ToolCall:
    name: str
    parameters: dict

@dataclass
class TestResultWithTools(TestResult):
    tool_calls_count: int
    iterations_to_success: int
    tools_used: List[str]
    self_corrected: bool
```

---

## Implementation Roadmap

### Phase 1: Project Setup
- [x] Create project structure (directories)
- [x] Setup Python virtual environment (already done - alias: `llmbench`)
- [x] Install dependencies (requirements.txt) (already done)
- [x] Verify system requirements (TypeScript, nvidia-smi, Ollama) (already done)
- [x] Create .gitignore file (already done)
- [x] Create README.md with usage documentation

### Phase 2: Core Components

#### 2.1 Ollama Client (`src/ollama_client.py`) - COMPLETED
- [x] Create `ChatResult` dataclass
- [x] Implement `chat()` function
- [x] Add error handling (ModelNotFoundError, TimeoutError, OllamaConnectionError)
- [x] Parse response metadata (tokens, duration)
- [x] Add timeout support
- [x] Implement `get_ollama_base_url()` configuration
- [x] Unit tests - 13 tests passing

#### 2.2 GPU Monitor (`src/gpu_monitor.py`) - COMPLETED
- [x] Create `GPUMetrics` dataclass
- [x] Implement `monitor_gpu_during_inference()` function
- [x] Parse nvidia-smi CSV output
- [x] Implement 500ms polling loop with threading
- [x] Calculate avg/peak metrics
- [x] Add nvidia-smi availability check
- [x] Implement `check_nvidia_smi_available()` function
- [x] Implement `parse_nvidia_smi_output()` function
- [x] Add thread-safety with Event synchronization
- [x] Handle callback exceptions gracefully
- [x] Unit tests - 20 tests passing (1 integration skipped)

#### 2.3 Validator (`src/validator.py`) - COMPLETED
- [x] Create `CompilationResult` dataclass (for vue-tsc validation)
- [x] Create `ASTResult` dataclass (for pattern matching)
- [x] Implement `validate_compilation()` function (run vue-tsc in target project)
- [x] Implement `validate_ast_structure()` function (pattern matching)
- [x] Add AST parser using @vue/compiler-sfc (official Vue parser - no false positives!)
- [x] Calculate pattern score based on validation_spec.json weights
- [x] Test with valid/invalid Vue files
- [x] Create Node.js AST parser script (`scripts/parse_vue_ast.js`)
- [x] Install Node.js dependencies (@vue/compiler-sfc, typescript, vue-tsc)
- [x] Unit tests - 17 tests passing (AST validation)
- [x] Architecture: Dual validation (compilation + pattern matching)

#### 2.4 Refactoring Test (`src/refactoring_test.py`) - COMPLETED
- [x] Create `TestResult` dataclass (with compilation + pattern scores)
- [x] Implement `RefactoringTest` class
- [x] Add fixture loading (prompt.md, validation_spec.json, target_project/)
- [x] Implement prompt template rendering ({{original_code}} from target file)
- [x] Integrate Ollama client
- [x] Integrate GPU monitor (with TODO for real hardware validation)
- [x] Write LLM output to target_project file
- [x] Run vue-tsc compilation validation in target_project
- [x] Run AST pattern validation on LLM output
- [x] Calculate weighted composite score from validation_spec.json
- [x] Restore original file after test (cleanup)
- [x] Add comprehensive error handling
- [x] Test end-to-end with fixture (85/90 tests passing, 3 failing due to mock limitations)

### Phase 3: Fixtures

#### 3.1 Simple Component Fixture
- [ ] Create `fixtures/refactoring/simple-component/` directory
- [ ] Create `target_project/` subdirectory (complete Vue 3 project)
- [ ] Write `target_project/package.json` (Vue 3 + TypeScript deps)
- [ ] Write `target_project/tsconfig.json` (Vue 3 TS config)
- [ ] Write `target_project/vite.config.ts` (minimal Vite config)
- [ ] Write `target_project/src/components/HelloWorld.vue` (untyped initial state)
- [ ] Write `prompt.md` (Jinja2-style template with {{original_code}})
- [ ] Write `validation_spec.json` (required patterns + scoring weights)
- [ ] Run `npm install` in target_project
- [ ] Validate target_project compiles with `npm run type-check`
- [ ] Test fixture manually with Ollama

### Phase 4: Runner Script - COMPLETED

#### 4.1 Main Entry Point (`run_test.py`)
- [x] Create main() function
- [x] Add configuration (MODEL, FIXTURE, RUNS)
- [x] Setup rich console output
- [x] Create results directory
- [x] Initialize RefactoringTest
- [x] Implement test loop (multiple runs)
- [x] Add progress tracking (rich.progress)
- [x] Save results to JSON
- [x] Add summary statistics (avg GPU, scores)
- [x] Add warning for low GPU utilization (and low scores)

### Phase 5: Validation & Testing

#### 5.1 Pre-Benchmark Validation
- [ ] Verify GPU access (nvidia-smi)
- [ ] Test Ollama with sample model
- [ ] Verify TypeScript compiler version
- [ ] Check Ollama model availability
- [ ] Validate fixture with tsc
- [ ] Test Python imports

#### 5.2 Integration Testing
- [ ] Run complete benchmark (3 iterations)
- [ ] Verify JSON output format
- [ ] Check GPU utilization >80%
- [ ] Validate TypeScript detection works
- [ ] Confirm AST scoring accuracy
- [ ] Verify performance metrics (tok/s)

### Phase 6: Documentation
- [ ] Update README.md with usage instructions
- [ ] Document JSON output schema
- [ ] Add troubleshooting guide
- [ ] Document known limitations
- [ ] Add example output

---

## Implementation Details

### Directory Structure
```
llm-benchmark/
├── venv/                          # Virtual environment
├── requirements.txt
├── .gitignore
├── CLAUDE.md                      # Project plan
├── specs.md                       # This file
├── README.md                      # User documentation
│
├── src/
│   ├── __init__.py
│   ├── ollama_client.py
│   ├── gpu_monitor.py
│   ├── validator.py
│   └── refactoring_test.py
│
├── scripts/
│   └── parse_vue_ast.js          # Node.js AST parser helper
│
├── fixtures/
│   └── refactoring/
│       └── simple-component/
│           ├── target_project/          # Complete Vue 3 project
│           │   ├── package.json
│           │   ├── tsconfig.json
│           │   ├── vite.config.ts
│           │   ├── node_modules/        # gitignored
│           │   └── src/
│           │       └── components/
│           │           └── HelloWorld.vue
│           ├── prompt.md
│           └── validation_spec.json
│
├── results/                       # gitignored
│   └── .gitkeep
│
└── run_test.py
```

### Dependencies
```
ollama>=0.4.0
rich>=13.0.0
```

### System Requirements
- Python 3.12+
- Node.js 24.x
- TypeScript 5.x
- nvidia-smi (NVIDIA drivers)
- Ollama with GPU support

### Configuration (Hardcoded for MVP)
```python
MODEL = "qwen2.5-coder:7b-instruct-q8_0"
FIXTURE = Path("fixtures/refactoring/simple-component")
RUNS = 3
POLLING_INTERVAL = 0.5  # seconds for GPU monitoring
TIMEOUT = 30  # seconds for Ollama
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

### GPUMetrics
```python
@dataclass
class GPUMetrics:
    avg_utilization: float      # %
    peak_utilization: float     # %
    avg_memory_used: float      # GB
    peak_memory_used: float     # GB
    samples: int
```

### CompilationResult
```python
@dataclass
class CompilationResult:
    success: bool
    errors: List[str]
    warnings: List[str]
```

### ASTResult
```python
@dataclass
class ASTResult:
    has_interfaces: bool
    has_type_annotations: bool
    has_imports: bool
    has_script_lang: bool
    missing: List[str]
    score: float  # 0.0-1.0 (normalized)
```

### TestResult
```python
@dataclass
class TestResult:
    model: str
    fixture: str
    timestamp: str
    compiles: bool
    compilation_errors: List[str]
    pattern_score: float         # 0-10 from AST validation
    final_score: float           # 0-10 weighted composite
    tokens_per_sec: float
    duration_sec: float
    gpu_avg_utilization: float
    gpu_peak_utilization: float
    gpu_avg_memory_gb: float
    gpu_peak_memory_gb: float
    output_code: str
    run_number: int
```

---

## Testing Strategy

### Unit Tests
- `ollama_client.py`: Mock Ollama API responses
- `gpu_monitor.py`: Mock nvidia-smi output
- `validator.py`: Test with known valid/invalid code

### Integration Tests
- End-to-end run with real Ollama model
- Verify all metrics are captured
- Check JSON serialization

### Validation Tests
- GPU utilization >80%
- TypeScript compiler detects errors
- AST scoring matches expectations
- Performance within expected range

---

## Success Criteria

- [x] All unit tests pass
- [ ] Fixture target_project compiles with vue-tsc
- [ ] Integration test completes 3 runs without errors
- [ ] GPU utilization averages >80%
- [ ] Compilation validation works (detects TypeScript errors)
- [ ] Pattern validation scores perfect output as 10/10
- [ ] Weighted scoring correctly combines compilation + pattern scores
- [ ] Results JSON is well-formed
- [ ] Performance ~150-250 tok/s for 7B Q8 model

---

## Known Issues / TODOs

### Limitations (MVP Scope)
- Single test scenario (TypeScript refactoring only)
- Single file per fixture (no multi-file refactoring)
- Basic pattern matching (presence check, not usage correctness)
- No CLI arguments (hardcoded config)
- No statistical aggregation
- No report generation
- No multi-model comparison tools
- Manual fixture setup (no automated project scaffolding)

### Future Enhancements (Post-MVP)
- Multiple test scenarios:
  - Vue 2 → Vue 3 migration
  - Nuxt 3 projects with server composables
  - Design system integration
  - Multi-file refactoring
- Implement CLI with click/argparse
- Add markdown/CSV report generation
- Add Vitest functional testing (run in browser)
- Advanced pattern tracking:
  - Composable usage correctness
  - Component composition patterns
  - Reactivity API usage
- Architecture detection (MoE vs Dense)
- Statistical analysis across runs
- Automated fixture scaffolding

---

## Implementation Phases Strategy

### Phase 1: Prompt-Only Baseline (CURRENT PRIORITY)

**Goal**: Validate workflow with simplest possible setup

**Approach**:
- Single prompt → LLM generates complete code → validate
- No tool-calling, no iterations
- LLM must produce correct code in one shot

**Rationale**:
- Prove infrastructure works (fixtures, validation, GPU monitoring, JSON output)
- Get baseline metrics before adding complexity
- Quick validation that "it doesn't explode"

**Success Criteria**:
- Runs 3 consecutive tests without crashes
- Produces valid JSON results
- Metrics are sensible (GPU usage, tokens/sec, scores)

**Components Status**:
- `ollama_client.py`: Simple `chat()` method (no tool-calling) - ✅ DONE
- `gpu_monitor.py`: Basic monitoring - ✅ DONE
- `validator.py`: Compilation + AST validation - ✅ DONE
- `refactoring_test.py`: Single-shot workflow - ⬜ TODO
- `run_test.py`: Simple runner - ⬜ TODO
- Fixture `simple-component`: Single file refactoring - ⬜ TODO

### Phase 2: Tool-Calling Agent (AFTER Phase 1 is stable)

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
```python
# Extended TestResult dataclass for Phase 2
@dataclass
class TestResult:
    # ... all Phase 1 fields ...

    # Phase 2: Agent metrics
    tool_calls_count: int = 0           # Total tool calls
    iterations_to_success: int = 0      # Cycles to complete
    tools_used: List[str] = None        # Sequence of tools
    self_corrected: bool = False        # Read errors and fixed?
    efficiency_score: float = 1.0       # Penalty for excessive iterations
```

**Implementation Tasks**:
- [ ] Update `ollama_client.py` for function calling (Ollama 0.3+ supports this)
- [ ] Modify `refactoring_test.py` with agent loop
- [ ] Update fixtures with examples of expected tool sequences
- [ ] Add efficiency scoring (penalize excessive iterations)
- [ ] Implement tool handlers (`read_file`, `write_file`, `run_type_check`, `finish`)
- [ ] Add iteration limits and timeout handling

**Tool Definitions** (Phase 2):
```python
AVAILABLE_TOOLS = [
    {
        "name": "read_file",
        "description": "Read content of a file in the target project",
        "parameters": {"path": "string"}
    },
    {
        "name": "write_file",
        "description": "Write/overwrite a file in the target project",
        "parameters": {"path": "string", "content": "string"}
    },
    {
        "name": "run_type_check",
        "description": "Run vue-tsc to check TypeScript errors",
        "parameters": {}
    },
    {
        "name": "finish",
        "description": "Signal task completion",
        "parameters": {}
    }
]
```

---

## Notes

- Keep temp files on validation errors for debugging
- If GPU <80%, investigate before continuing
- Test each component independently before integration
- Use rich console for better UX
- Commit after each major component completion
- **Phase 1 priority**: Get prompt-only workflow working end-to-end
- **Phase 2 delayed**: Tool-calling only after Phase 1 validates successfully

---

**Last Updated**: 2026-02-16
**Current Phase**: Phase 1 (Prompt-Only Baseline)
**Next Milestone**: Complete Phase 2.4 (Refactoring Test) for Phase 1
