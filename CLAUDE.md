# LLM Benchmark Suite - Implementation Plan v1.0

**Project**: Local LLM Benchmarking Tool for Vue.js/Nuxt/TypeScript Development
**Date**: 2025-01-17
**Phase**: MVP (Minimum Viable Product)

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

Create a tool to benchmark LLMs locally using Ollama. The tool should be able to run a single test type, validate the result and provide metrics.

---

## Scope MVP

### What's IN
- **Single test type**: Refactoring accuracy
- **Single validator**: TypeScript compilation + AST structure check
- **GPU monitoring**: Real-time nvidia-smi integration
- **Basic metrics**: compile status, tokens/sec, GPU utilization, duration
- **Single fixture**: Vue component refactoring (props typing)
- **Raw JSON output**: Structured results for future aggregation
- **Simple runner**: Python script with hardcoded parameters

### What's OUT (Future Phases)
- Multiple test types (context window, consistency, etc.)
- CLI with argparse/click
- Report generation (Markdown/CSV)
- Data aggregation and statistics
- Multiple fixtures per test type
- Vitest functional testing (AST check only for MVP)
- Architecture-aware comparisons (MoE vs Dense)
- Scenario-based scoring

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
│   ├── validator.py              # TypeScript + AST validation
│   └── refactoring_test.py       # Refactoring test runner
│
├── fixtures/
│   └── refactoring/
│       └── simple-component/      # First test fixture
│           ├── input.vue          # Untyped component
│           ├── expected.vue       # Typed component (reference)
│           ├── prompt.md          # Jinja2 template for LLM prompt
│           └── ast_checks.json    # Expected AST structures
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

**Purpose**: Validate LLM output (TypeScript compilation + AST structure)

**Key Functions**:
```python
def validate_typescript(code: str, temp_dir: Path) -> TypeScriptResult:
    """
    Check if Vue component compiles with TypeScript
    
    Returns:
        TypeScriptResult dataclass with:
        - compiles: bool
        - errors: List[str]
        - temp_file: Path
    """

def validate_ast_structure(code: str, expected_structures: dict) -> ASTResult:
    """
    Check if code contains expected AST structures
    
    Expected structures (from ast_checks.json):
    {
      "interfaces": ["ComponentProps"],
      "type_annotations": ["props: ComponentProps"],
      "imports": ["import type { ComponentProps }"]
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

**TypeScript Validation**:
- Write code to temp file: `{temp_dir}/output_{uuid}.vue`
- Run: `tsc --noEmit --skipLibCheck {temp_file}`
- Parse stderr for errors
- Keep temp file for debugging (cleanup at end of run)
- Return bool + error list

**AST Validation**:
- Use regex or simple string matching for MVP (no full parser yet)
- Check for presence of:
  - `interface {Name} {` (interfaces)
  - `: {Type}` after variable/param (type annotations)
  - `import type` or `import {` (imports)
- Score: 10 if all present, proportional if partial
- Log what's missing for debugging

**Trade-offs**:
- MVP uses regex, not proper AST parser (faster to implement)
- False positives possible (commented code matches)
- Good enough to validate basic refactoring quality
- Future: migrate to proper TypeScript AST parser

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
            - ast_score: float
            - tokens_per_sec: float
            - duration_sec: float
            - gpu_avg_utilization: float
            - gpu_peak_memory_gb: float
            - output_code: str
            - errors: List[str]
            - timestamp: str
        """
```

**Workflow**:
1. Load fixture files (input, expected, prompt, ast_checks)
2. Render prompt: replace `{{input_code}}` in prompt.md with input.vue content
3. Wrap Ollama call with GPU monitor
4. Run TypeScript validation on output
5. Run AST validation on output
6. Calculate composite score (binary compile × AST score)
7. Return structured result

**Scoring Logic**:
```python
if not compiles:
    final_score = 0.0
else:
    final_score = ast_score  # 0-10 from AST validation
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
        status = "✓" if result.compiles else "✗"
        console.print(
            f"{status} Run {i+1}: "
            f"Score={result.ast_score:.1f}/10, "
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

### `input.vue`
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

### `expected.vue`
```vue
<script setup lang="ts">
interface ComponentProps {
  title: string
  count: number
  items: string[]
}

const props = defineProps<ComponentProps>()

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
- Define an interface for props with proper types
- Use `defineProps<Interface>()` syntax
- Maintain exact same functionality
- Keep template unchanged

Input code:
```vue
{{input_code}}
```

Output only the refactored component, no explanations.
```

### `ast_checks.json`
```json
{
  "interfaces": ["ComponentProps"],
  "type_annotations": ["defineProps<ComponentProps>"],
  "script_lang": ["<script setup lang=\"ts\">"],
  "imports": []
}
```

**AST Scoring**:
- `interfaces` present: +3.3 points
- `type_annotations` present: +3.3 points  
- `script_lang` present: +3.4 points
- Max score: 10.0

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
- Node.js 24.x (installed, for `tsc`)
- TypeScript compiler: `npm install -g typescript`
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

2. **TypeScript Compiler**:
   ```bash
   tsc --version  # Should be 5.x
   ```

3. **Ollama Models**:
   ```bash
   ollama list | grep qwen2.5-coder:7b-instruct-q8_0
   ```

4. **Fixture Validity**:
   ```bash
   tsc --noEmit fixtures/refactoring/simple-component/expected.vue
   # Should compile with no errors
   ```

5. **Python Environment**:
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
    "ast_score": 10.0,
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
3. ✅ **TypeScript validation** correctly identifies compile errors
4. ✅ **AST validation** scores expected output as 10/10
5. ✅ **Results JSON** is well-formed and contains all metrics
6. ✅ **Performance** matches expectations (~150-250 tok/s for 7B Q8 model)

---

## Known Limitations (MVP)

1. **Single test type**: Only refactoring, no context window/consistency tests
2. **No aggregation**: Raw JSON only, no statistics or reports
3. **AST validation**: Regex-based, may have false positives
4. **No Vitest**: Functional testing postponed to future phase
5. **Hardcoded config**: No CLI arguments, edit source to change model/fixture
6. **No multi-model comparison**: Run script multiple times manually
7. **No architecture detection**: MoE vs Dense distinction not tracked yet

---

## Next Steps (Post-MVP)

After MVP validation:

1. Add second fixture (`complex-component` with composables)
2. Implement aggregation (mean, stddev across runs)
3. Add Markdown report generation
4. CLI with click (model, fixture, runs arguments)
5. Add context window test type
6. Implement proper TypeScript AST parser
7. Add Vitest functional validation
8. Model architecture detection (MoE vs Dense)

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