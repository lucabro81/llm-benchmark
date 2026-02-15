# LLM Benchmark - Implementation Specs & Checklist

**Project**: Local LLM Benchmarking Tool
**Created**: 2026-02-01
**Status**: Planning Phase

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

#### 2.4 Refactoring Test (`src/refactoring_test.py`)
- [ ] Create `TestResult` dataclass (with compilation + pattern scores)
- [ ] Implement `RefactoringTest` class
- [ ] Add fixture loading (prompt.md, validation_spec.json, target_project/)
- [ ] Implement prompt template rendering ({{original_code}} from target file)
- [ ] Integrate Ollama client
- [ ] Integrate GPU monitor
- [ ] Write LLM output to target_project file
- [ ] Run vue-tsc compilation validation in target_project
- [ ] Run AST pattern validation on LLM output
- [ ] Calculate weighted composite score from validation_spec.json
- [ ] Restore original file after test (cleanup)
- [ ] Add comprehensive error handling
- [ ] Test end-to-end with fixture

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

### Phase 4: Runner Script

#### 4.1 Main Entry Point (`run_test.py`)
- [ ] Create main() function
- [ ] Add configuration (MODEL, FIXTURE, RUNS)
- [ ] Setup rich console output
- [ ] Create results directory
- [ ] Initialize RefactoringTest
- [ ] Implement test loop (multiple runs)
- [ ] Add progress tracking (rich.progress)
- [ ] Save results to JSON
- [ ] Add summary statistics (avg GPU, scores)
- [ ] Add warning for low GPU utilization

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

## Notes

- Keep temp files on validation errors for debugging
- If GPU <80%, investigate before continuing
- Test each component independently before integration
- Use rich console for better UX
- Commit after each major component completion

---

**Last Updated**: 2026-02-15
**Next Milestone**: Complete Phase 2.4 (Refactoring Test)
