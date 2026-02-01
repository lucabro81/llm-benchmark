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

#### 2.3 Validator (`src/validator.py`)
- [ ] Create `TypeScriptResult` dataclass
- [ ] Create `ASTResult` dataclass
- [ ] Implement `validate_typescript()` function
- [ ] Setup temp file handling (UUID naming)
- [ ] Run tsc compilation check
- [ ] Parse tsc error output
- [ ] Implement `validate_ast_structure()` function
- [ ] Add regex checks (interfaces, type annotations, imports)
- [ ] Calculate AST score (0-10)
- [ ] Test with valid/invalid Vue files

#### 2.4 Refactoring Test (`src/refactoring_test.py`)
- [ ] Create `TestResult` dataclass
- [ ] Implement `RefactoringTest` class
- [ ] Add fixture loading (input.vue, expected.vue, prompt.md, ast_checks.json)
- [ ] Implement prompt template rendering
- [ ] Integrate Ollama client
- [ ] Integrate GPU monitor
- [ ] Run validators on output
- [ ] Calculate composite score
- [ ] Add comprehensive error handling
- [ ] Test end-to-end with dummy fixture

### Phase 3: Fixtures

#### 3.1 Simple Component Fixture
- [ ] Create `fixtures/refactoring/simple-component/` directory
- [ ] Write `input.vue` (untyped component)
- [ ] Write `expected.vue` (typed component)
- [ ] Write `prompt.md` (Jinja2-style template)
- [ ] Write `ast_checks.json` (expected structures)
- [ ] Validate expected.vue compiles with tsc
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
├── fixtures/
│   └── refactoring/
│       └── simple-component/
│           ├── input.vue
│           ├── expected.vue
│           ├── prompt.md
│           └── ast_checks.json
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

### TypeScriptResult
```python
@dataclass
class TypeScriptResult:
    compiles: bool
    errors: List[str]
    temp_file: Path
```

### ASTResult
```python
@dataclass
class ASTResult:
    has_interfaces: bool
    has_type_annotations: bool
    has_script_lang: bool
    missing: List[str]
    score: float  # 0-10
```

### TestResult
```python
@dataclass
class TestResult:
    model: str
    fixture: str
    timestamp: str
    compiles: bool
    ast_score: float
    tokens_per_sec: float
    duration_sec: float
    gpu_avg_utilization: float
    gpu_peak_utilization: float
    gpu_avg_memory_gb: float
    gpu_peak_memory_gb: float
    output_code: str
    errors: List[str]
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
- [ ] Integration test completes 3 runs without errors
- [ ] GPU utilization averages >80%
- [ ] TypeScript validation works correctly
- [ ] AST validation scores expected.vue as 10/10
- [ ] Results JSON is well-formed
- [ ] Performance ~150-250 tok/s for 7B Q8 model

---

## Known Issues / TODOs

### Limitations (MVP Scope)
- Regex-based AST validation (may have false positives)
- No CLI arguments (hardcoded config)
- Single test type only
- No statistical aggregation
- No report generation
- No multi-model comparison tools

### Future Enhancements (Post-MVP)
- Add proper TypeScript AST parser
- Implement CLI with click/argparse
- Add markdown/CSV report generation
- Support multiple test types (context window, consistency)
- Add Vitest functional testing
- Architecture detection (MoE vs Dense)
- Statistical analysis across runs

---

## Notes

- Keep temp files on validation errors for debugging
- If GPU <80%, investigate before continuing
- Test each component independently before integration
- Use rich console for better UX
- Commit after each major component completion

---

**Last Updated**: 2026-02-01
**Next Milestone**: Complete Phase 1 (Project Setup)
