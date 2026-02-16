# LLM Benchmark Suite - Implementation Plan v1.0

**Project**: Local LLM Benchmarking Tool for Vue.js/Nuxt/TypeScript Development
**Date**: 2025-01-17
**Phase**: MVP Phase 1 (Prompt-Only Baseline)

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
- Runs 3 consecutive tests without crashes
- Produces valid JSON results
- Metrics are sensible (GPU usage, tokens/sec, scores)

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
- Modify `refactoring_test.py` with agent loop
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

### What's IN
- **Single test scenario**: TypeScript refactoring in Vue 3 project
- **Self-contained fixtures**: Each fixture includes a complete Vue project with dependencies
- **Dual validation**: TypeScript compilation (vue-tsc) + AST pattern conformance
- **GPU monitoring**: Real-time nvidia-smi integration
- **Comprehensive metrics**: Compilation success, pattern conformance score, tokens/sec, GPU utilization, duration
- **In-place execution**: LLM modifies files directly in fixture's target project
- **Raw JSON output**: Structured results for future aggregation
- **Simple runner**: Python script with hardcoded parameters

### What's OUT (Future Phases)
- Multiple test scenarios (Vue 2→3 migration, Nuxt projects, design system integration)
- CLI with argparse/click
- Report generation (Markdown/CSV)
- Data aggregation and statistics
- Multiple fixtures per scenario
- Vitest functional testing (run code in browser)
- Architecture-aware comparisons (MoE vs Dense)
- Advanced pattern matching (composable usage tracking, component composition)

---

## Project Structure

```
~/Projects/llm-benchmark/
├── venv/                          # Python virtual environment (exists)
├── requirements.txt               # Python dependencies
├── .gitignore                     # Ignore venv/, results/, temp files
│
├── src/
│   ├── __init__.py
│   ├── ollama_client.py          # Ollama API wrapper + response parsing
│   ├── gpu_monitor.py            # nvidia-smi integration
│   ├── validator.py              # AST structure validation
│   └── refactoring_test.py       # Refactoring test runner
│
├── scripts/
│   └── parse_vue_ast.js          # Node.js AST parser helper
│
├── fixtures/
│   └── refactoring/
│       └── simple-component/           # First test fixture
│           ├── target_project/         # Complete Vue 3 project
│           │   ├── package.json        # Vue + TypeScript + deps
│           │   ├── tsconfig.json       # Vue 3 TS config
│           │   └── src/
│           │       └── components/
│           │           └── HelloWorld.vue  # File to be modified by LLM
│           ├── prompt.md               # Template with {{original_code}}
│           └── validation_spec.json    # Expected patterns + scoring weights
│
├── results/                       # gitignored, created at runtime
│   └── .gitkeep
│
└── run_test.py                    # Entry point script
```

---

## Component Specifications

### 1. `src/ollama_client.py`

**Purpose**: Wrapper for Ollama API with error handling and metrics extraction

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

**Error Handling**:
- Model not found → raise `ModelNotFoundError`
- Timeout exceeded → raise `TimeoutError`
- API connection issues → raise `OllamaConnectionError`
- Log all errors with context

**Implementation Notes**:
- Use `ollama.chat()` from Python SDK
- Set timeout via subprocess or async wrapper
- Parse response metadata for token counts
- Return structured dataclass, not raw dict

---

### 2. `src/gpu_monitor.py`

**Purpose**: Monitor GPU utilization during LLM inference using nvidia-smi

**Key Functions**:
```python
def monitor_gpu_during_inference(callback: Callable) -> GPUMetrics:
    """
    Monitor GPU while callback executes
    
    Polls nvidia-smi every 0.5s during execution
    
    Returns:
        GPUMetrics dataclass with:
        - avg_utilization: float (%)
        - peak_utilization: float (%)
        - avg_memory_used: float (GB)
        - peak_memory_used: float (GB)
        - samples: int
    """
```

**Implementation**:
- Run `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits` in loop
- Parse CSV output: `85, 12345` → 85% GPU, 12345 MB VRAM
- Poll every 500ms during inference
- Store samples and calculate avg/peak after callback completes
- Thread-safe if inference is async

**Validation**:
- Check `nvidia-smi` available at startup
- Warn if avg_utilization < 80% (config issue)
- Fail gracefully if nvidia-smi errors

---

### 3. `src/validator.py`

**Purpose**: Dual validation - compilation + pattern conformance

**Validation Architecture**:
```
LLM Output (written to target_project/src/...)
    ↓
[1] TypeScript Compilation (vue-tsc in target project context)
    ↓
[2] AST Pattern Matching (@vue/compiler-sfc + Babel)
    ↓
Composite Score
```

**Key Functions**:
```python
def validate_compilation(target_project: Path) -> CompilationResult:
    """
    Run vue-tsc in target project to verify code compiles.

    Returns:
        CompilationResult dataclass with:
        - success: bool
        - errors: List[str]
        - warnings: List[str]
    """

def validate_ast_structure(code: str, expected_structures: dict) -> ASTResult:
    """
    Check if code contains expected AST structures using official Vue parser

    Expected structures (from ast_checks.json):
    {
      "interfaces": ["ComponentProps"],
      "type_annotations": ["defineProps<ComponentProps>"],
      "script_lang": ["<script setup lang=\"ts\">"],
      "imports": []
    }

    Returns:
        ASTResult dataclass with:
        - has_interfaces: bool
        - has_type_annotations: bool
        - has_imports: bool
        - missing: List[str]
        - score: float (0-10)
    """
```

**Compilation Validation**:
- Executes `vue-tsc --noEmit` in target_project directory
- Full context: all dependencies, tsconfig, project structure
- Returns success/failure + TypeScript error messages
- No file copying - LLM output already written to target file

**AST Pattern Validation**:
- Uses **@vue/compiler-sfc** (official Vue SFC parser) + Babel TypeScript AST
- Calls Node.js helper script (`scripts/parse_vue_ast.js`) via subprocess
- Extracts TypeScript AST from `<script>` block
- Checks for specific patterns from `validation_spec.json`:
  - **interfaces**: Specific interface names (e.g., "ComponentProps", "UserProfile")
  - **type_annotations**: Specific type usages (e.g., "defineProps<ComponentProps>")
  - **imports**: Specific import paths (e.g., "@/composables/useAuth")
  - **composables**: Specific composable calls (e.g., "useAuth()", "useUser()")
  - **script_lang**: `lang="ts"` attribute
- Scoring: Configurable weights per pattern category from validation_spec.json
- No false positives from commented code (parses actual AST, not text)

**Scoring Model**:
```python
# From validation_spec.json
{
  "scoring": {
    "compilation": 0.5,      # 50% weight
    "pattern_match": 0.4,    # 40% weight
    "naming": 0.1            # 10% weight
  }
}

final_score = (
    compilation_success * weights["compilation"] +
    ast_conformance * weights["pattern_match"] +
    naming_conformance * weights["naming"]
) * 10  # Scale to 0-10
```

---

### 4. `src/refactoring_test.py`

**Purpose**: Orchestrate refactoring test execution

**Key Class**:
```python
class RefactoringTest:
    def __init__(self, model: str, fixture_path: Path):
        self.model = model
        self.fixture_path = fixture_path
        self.input_code = self._load_file("input.vue")
        self.expected_code = self._load_file("expected.vue")
        self.prompt_template = self._load_file("prompt.md")
        self.ast_checks = self._load_json("ast_checks.json")
    
    def run(self) -> TestResult:
        """
        Execute single test run
        
        Steps:
        1. Render prompt from template
        2. Monitor GPU + call Ollama
        3. Validate output (TypeScript + AST)
        4. Calculate score
        5. Return structured result
        
        Returns:
            TestResult dataclass with:
            - model: str
            - fixture: str
            - compiles: bool
            - compilation_errors: List[str]
            - pattern_score: float (0-10)
            - final_score: float (0-10, weighted)
            - tokens_per_sec: float
            - duration_sec: float
            - gpu_avg_utilization: float
            - gpu_peak_memory_gb: float
            - output_code: str
            - timestamp: str
        """
```

**Workflow**:
1. Load fixture (prompt.md, validation_spec.json)
2. Read original file from target_project (e.g., src/components/HelloWorld.vue)
3. Render prompt: replace `{{original_code}}` with file content
4. Wrap Ollama call with GPU monitor
5. Write LLM output back to target file
6. Run vue-tsc in target_project (compilation validation)
7. Run AST validation on LLM output (pattern conformance)
8. Calculate composite score based on validation_spec weights
9. Restore original file (cleanup for next run)
10. Return structured result

**Scoring Logic**:
```python
# Weighted scoring from validation_spec.json
compilation_score = 1.0 if compiles else 0.0
pattern_score = ast_result.score  # 0.0-1.0 based on patterns found
naming_score = naming_result.score  # 0.0-1.0 based on conventions

weights = validation_spec["scoring"]
final_score = (
    compilation_score * weights["compilation"] +
    pattern_score * weights["pattern_match"] +
    naming_score * weights["naming"]
) * 10  # Scale to 0-10
```

**Error Handling**:
- Model not found → propagate error (fail fast)
- Timeout → save partial result with error flag
- Validation errors → score=0, save errors in result

---

### 5. `run_test.py`

**Purpose**: Entry point script to run benchmark

**Implementation**:
```python
#!/usr/bin/env python3
from pathlib import Path
from src.refactoring_test import RefactoringTest
from rich.console import Console
from rich.progress import track
import json

console = Console()

# Configuration (hardcoded for MVP)
MODEL = "qwen2.5-coder:7b-instruct-q8_0"
FIXTURE = Path("fixtures/refactoring/simple-component")
RUNS = 3
OUTPUT_DIR = Path("results")

def main():
    console.print(f"[bold cyan]LLM Benchmark MVP[/bold cyan]")
    console.print(f"Model: [yellow]{MODEL}[/yellow]")
    console.print(f"Fixture: [yellow]{FIXTURE}[/yellow]")
    console.print(f"Runs: [yellow]{RUNS}[/yellow]\n")
    
    # Create results directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Initialize test
    test = RefactoringTest(model=MODEL, fixture_path=FIXTURE)
    
    # Run multiple times
    results = []
    for i in track(range(RUNS), description="Running tests..."):
        result = test.run()
        results.append(result)
        
        # Print summary
        compile_icon = "✓" if result.compiles else "✗"
        score_icon = "✓" if result.final_score >= 8.0 else "✗"
        console.print(
            f"{compile_icon} Compile | {score_icon} Score | Run {i+1}: "
            f"Final={result.final_score:.1f}/10 "
            f"(Pattern={result.pattern_score:.1f}), "
            f"Speed={result.tokens_per_sec:.1f} tok/s, "
            f"GPU={result.gpu_avg_utilization:.0f}%"
        )
    
    # Save raw results
    timestamp = results[0].timestamp.replace(":", "-")
    output_file = OUTPUT_DIR / f"{MODEL.replace(':', '_')}_refactoring_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump([r.__dict__ for r in results], f, indent=2)
    
    console.print(f"\n[green]✓ Results saved to {output_file}[/green]")
    
    # Warn if GPU utilization low
    avg_gpu = sum(r.gpu_avg_utilization for r in results) / len(results)
    if avg_gpu < 80:
        console.print(
            f"\n[yellow]⚠ Warning: Average GPU utilization is {avg_gpu:.0f}% (target >80%)[/yellow]"
        )

if __name__ == "__main__":
    main()
```

**Output Example**:
```
LLM Benchmark MVP
Model: qwen2.5-coder:7b-instruct-q8_0
Fixture: fixtures/refactoring/simple-component
Runs: 3

✓ Run 1: Score=9.0/10, Speed=185.3 tok/s, GPU=94%
✓ Run 2: Score=10.0/10, Speed=178.1 tok/s, GPU=92%
✓ Run 3: Score=8.0/10, Speed=181.7 tok/s, GPU=95%

✓ Results saved to results/qwen2.5-coder_7b-instruct-q8_0_refactoring_2025-01-17T14-23-45.json
```

---

## Fixture Specification: `simple-component`

### Directory Structure
```
fixtures/refactoring/simple-component/
├── target_project/              # Complete Vue 3 project
│   ├── package.json             # Vue 3.5 + TypeScript 5.x
│   ├── tsconfig.json            # Standard Vue 3 TS config
│   ├── vite.config.ts           # Minimal Vite config
│   └── src/
│       ├── components/
│       │   └── HelloWorld.vue   # File to be modified (untyped initially)
│       └── App.vue              # (optional, for context)
│
├── prompt.md                    # Jinja2 template
└── validation_spec.json         # Validation rules + scoring
```

### `target_project/package.json`
```json
{
  "name": "simple-component-fixture",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "type-check": "vue-tsc --noEmit"
  },
  "dependencies": {
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "@vue/compiler-sfc": "^3.5.0",
    "typescript": "^5.6.0",
    "vue-tsc": "^2.2.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-vue": "^5.2.0"
  }
}
```

### `target_project/src/components/HelloWorld.vue` (original state)
```vue
<script setup>
const props = defineProps({
  title: String,
  count: Number,
  items: Array
})

const doubled = computed(() => props.count * 2)
</script>

<template>
  <div>
    <h1>{{ title }}</h1>
    <p>Count: {{ count }}, Doubled: {{ doubled }}</p>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
  </div>
</template>
```

### `prompt.md`
```markdown
You are a Vue.js expert. Refactor the following component to add TypeScript type safety.

Requirements:
- Add `lang="ts"` to script tag
- Define an interface named `HelloWorldProps` for props with proper types
- Use `defineProps<HelloWorldProps>()` syntax
- Maintain exact same functionality
- Keep template unchanged

Original code:
```vue
{{original_code}}
```

Output ONLY the complete refactored component code, no explanations.
```

### `validation_spec.json`
```json
{
  "target_file": "src/components/HelloWorld.vue",
  "task_description": "Add TypeScript types to Vue 3 component props",

  "required_patterns": {
    "interfaces": ["HelloWorldProps"],
    "type_annotations": ["defineProps<HelloWorldProps>"],
    "script_lang": "ts",
    "imports": []
  },

  "naming_conventions": {
    "interfaces": "PascalCase",
    "props_interface_suffix": "Props"
  },

  "scoring": {
    "compilation": 0.5,
    "pattern_match": 0.4,
    "naming": 0.1
  }
}
```

### Expected LLM Output (reference)
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

<template>
  <div>
    <h1>{{ title }}</h1>
    <p>Count: {{ count }}, Doubled: {{ doubled }}</p>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
  </div>
</template>
```

**Scoring Breakdown**:
- Compilation (50%): ✓ Compiles with vue-tsc = 5.0 points
- Pattern Match (40%):
  - Has interface "HelloWorldProps": ✓ = 1.3 points
  - Has type annotation "defineProps<HelloWorldProps>": ✓ = 1.3 points
  - Has script lang="ts": ✓ = 1.4 points
  - Total: 4.0 points
- Naming (10%): Interface is PascalCase with "Props" suffix: ✓ = 1.0 point
- **Final Score: 10.0/10**

---

## Dependencies

### `requirements.txt`
```
ollama>=0.4.0
rich>=13.0.0
```

**Installation**:
```bash
cd ~/Projects/llm-benchmark
source venv/bin/activate
pip install -r requirements.txt
```

### System Requirements
- Python 3.12+ (installed)
- Node.js 24.x (installed, for AST parser + vue-tsc)
- Global tools: `npm install --save-dev @vue/compiler-sfc` (for AST parser script)
- Per-fixture dependencies: `cd fixtures/*/target_project && npm install` (for vue-tsc)
- nvidia-smi (pre-installed with NVIDIA drivers)
- Ollama running with GPU support

---

## Validation Checklist (Pre-Benchmark)

Before running benchmarks, verify:

1. **GPU Access**:
   ```bash
   nvidia-smi  # Should show GB10 GPU
   ollama run qwen2.5-coder:7b-instruct-q8_0 "hello" --verbose
   # Monitor GPU usage during generation
   ```

2. **Node.js Dependencies**:
   ```bash
   node --version  # Should be 24.x
   node -e "console.log(require('@vue/compiler-sfc').parse)"  # Should print function

   # Install fixture dependencies
   cd fixtures/refactoring/simple-component/target_project
   npm install
   npm run type-check  # Should pass for original untyped code (with warnings)
   ```

3. **Ollama Models**:
   ```bash
   ollama list | grep qwen2.5-coder:7b-instruct-q8_0
   ```

4. **Python Environment**:
   ```bash
   source venv/bin/activate
   python -c "import ollama, rich; print('OK')"
   ```

---

## Expected Output Format

### JSON Result Structure
```json
[
  {
    "model": "qwen2.5-coder:7b-instruct-q8_0",
    "fixture": "simple-component",
    "timestamp": "2025-01-17T14:23:45",
    "compiles": true,
    "compilation_errors": [],
    "pattern_score": 4.0,
    "final_score": 10.0,
    "tokens_per_sec": 185.3,
    "duration_sec": 4.2,
    "gpu_avg_utilization": 94.2,
    "gpu_peak_utilization": 98.1,
    "gpu_avg_memory_gb": 11.4,
    "gpu_peak_memory_gb": 12.1,
    "output_code": "<script setup lang=\"ts\">...",
    "errors": [],
    "run_number": 1
  },
  {
    "model": "qwen2.5-coder:7b-instruct-q8_0",
    "fixture": "simple-component",
    ...
    "run_number": 2
  },
  {
    ...
    "run_number": 3
  }
]
```

---

## Success Criteria

MVP is successful when:

1. ✅ **Runs without errors** on 3 consecutive tests
2. ✅ **GPU utilization** averages >80% during inference
3. ✅ **Compilation** succeeds with vue-tsc in target project
4. ✅ **Pattern validation** scores expected output as 10/10
5. ✅ **Results JSON** is well-formed and contains all metrics
6. ✅ **Performance** matches expectations (~150-250 tok/s for 7B Q8 model)

---

## Known Limitations (MVP)

1. **Single test scenario**: Only TypeScript refactoring, no Vue 2→3 migration, Nuxt, or design system scenarios
2. **No aggregation**: Raw JSON only, no statistics or reports
3. **Basic pattern matching**: Only checks for presence of patterns, not semantic correctness or usage patterns
4. **No Vitest**: Functional testing (running in browser) postponed to future phase
5. **Hardcoded config**: No CLI arguments, edit source to change model/fixture
6. **No multi-model comparison**: Run script multiple times manually
7. **No architecture detection**: MoE vs Dense distinction not tracked yet
8. **Single file per fixture**: LLM modifies one file at a time, no multi-file refactoring

---

## Next Steps (Post-MVP)

After MVP validation:

1. Add more scenarios:
   - Vue 2 → Vue 3 migration (Options API → Composition API)
   - Nuxt 3 project with server composables
   - Design system integration (use specific components library)
   - Complex refactoring with multiple files
2. Implement aggregation (mean, stddev across runs)
3. Add Markdown report generation
4. CLI with click (model, fixture, runs arguments)
5. Add context window test type
6. Add Vitest functional validation (run generated code in browser)
7. Model architecture detection (MoE vs Dense)
8. Advanced pattern tracking:
   - Composable usage correctness (not just presence)
   - Component composition patterns
   - Reactivity API usage (ref/reactive/computed)
9. Multi-file refactoring support

---

## Notes

- MVP focuses on **proving the workflow**, not completeness
- If GPU utilization is low, stop and debug before continuing
- If AST validation is too noisy, simplify checks
- Keep temp files on error for manual inspection
- Expect ~30 minutes of implementation for MVP

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-17  
**Status**: Ready for implementation