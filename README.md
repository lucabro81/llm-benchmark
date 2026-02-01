# LLM Benchmark Suite

Local benchmarking tool for testing LLM performance on Vue.js/Nuxt/TypeScript development tasks using Ollama.

## Overview

This tool benchmarks LLMs on real-world development tasks by:
- Running refactoring challenges (adding TypeScript type safety to Vue components)
- Validating output with TypeScript compiler and AST structure checks
- Monitoring GPU utilization in real-time
- Collecting performance metrics (tokens/sec, duration, GPU usage)

## Features

- **Single Test Type (MVP)**: Refactoring accuracy for Vue.js components
- **Validation**: TypeScript compilation + AST structure verification
- **GPU Monitoring**: Real-time nvidia-smi integration
- **Metrics**: Compilation status, tokens/sec, GPU utilization, duration
- **Structured Output**: JSON results for analysis

## Requirements

### System
- Python 3.12+
- Node.js 24.x with TypeScript 5.x
- **NVIDIA GPU with drivers (nvidia-smi)** - Required for GPU monitoring
  - Tests will mock GPU on systems without NVIDIA hardware
  - Integration tests are skipped automatically on non-GPU systems
- Ollama with GPU support (recommended) or CPU mode

### Python Dependencies
See [requirements.txt](requirements.txt)

## Installation

### 1. Clone and Setup Virtual Environment
```bash
cd ~/Projects/llm-benchmark
python3 -m venv venv

# Activate with alias (recommended)
alias llmbench='source ~/Projects/llm-benchmark/venv/bin/activate'
llmbench

# Or activate manually
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install TypeScript
```bash
npm install -g typescript
```

### 4. Verify Ollama
```bash
ollama list  # Check available models
nvidia-smi   # Verify GPU access
```

## Configuration

The tool uses environment variables for configuration. Create a `.env` file in the project root:

```bash
# .env
OLLAMA_BASE_URL=http://localhost:11434  # Optional, defaults to localhost
```

Or export environment variables:
```bash
export OLLAMA_BASE_URL=http://192.168.1.100:11434
```

## Usage

### Run Tests (Development)
```bash
# Activate environment
llmbench  # or: source venv/bin/activate

# Run all tests
pytest

# Run specific test module
pytest tests/test_ollama_client.py -v

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

### Run Benchmark (Coming Soon)
```bash
# This will be available after MVP completion
python run_test.py
```

## Project Structure

```
llm-benchmark/
├── src/                      # Core modules
│   ├── __init__.py
│   ├── ollama_client.py     # [DONE] Ollama API wrapper
│   ├── gpu_monitor.py       # [TODO] GPU monitoring
│   ├── validator.py         # [TODO] TypeScript/AST validation
│   └── refactoring_test.py  # [TODO] Test orchestration
│
├── tests/                    # Test suite (TDD)
│   ├── test_ollama_client.py   # [DONE] 13 tests passing
│   ├── test_gpu_monitor.py     # [TODO] Coming next
│   └── ...
│
├── fixtures/                 # Test fixtures
│   └── refactoring/
│       └── simple-component/
│           ├── input.vue      # Untyped Vue component
│           ├── expected.vue   # Typed reference
│           ├── prompt.md      # LLM prompt template
│           └── ast_checks.json
│
├── results/                  # Benchmark outputs (gitignored)
│
├── .env                      # Configuration (gitignored)
├── requirements.txt          # Python dependencies
├── CLAUDE.md                 # Detailed implementation plan
└── specs.md                  # Development checklist
```

## Available Commands

### Environment Management
```bash
# Activate virtual environment
llmbench  # Using alias
source venv/bin/activate  # Manual activation

# Deactivate
deactivate

# Update dependencies
pip install -r requirements.txt --upgrade
```

### Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_ollama_client.py

# Run specific test class
pytest tests/test_ollama_client.py::TestChatFunction

# Run specific test
pytest tests/test_ollama_client.py::TestChatFunction::test_successful_chat_call

# Run with coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Run only unit tests (skip integration)
pytest -m "not integration"

# Run integration tests (requires NVIDIA GPU)
# Note: Integration tests are skipped by default as they require:
# - Physical NVIDIA GPU with drivers installed
# - nvidia-smi available in PATH
pytest -m integration -v
```

**Note on Integration Tests:**
- Integration tests are marked with `@pytest.mark.integration` and `@pytest.mark.skip`
- They test real hardware (nvidia-smi, actual Ollama) instead of mocks
- Skipped by default on machines without NVIDIA GPU
- Run them manually only on GPU-enabled systems

### Code Quality
```bash
# Format code with black
black src/ tests/

# Lint with flake8
flake8 src/ tests/

# Type checking with mypy
mypy src/

# Sort imports
isort src/ tests/
```

### Ollama Operations
```bash
# List available models
ollama list

# Pull a model
ollama pull qwen2.5-coder:7b-instruct-q8_0

# Test model manually
ollama run qwen2.5-coder:7b-instruct-q8_0 "Say hello"

# Check Ollama service
curl http://localhost:11434/api/tags
```

### GPU Monitoring
```bash
# Check GPU status
nvidia-smi

# Monitor GPU in real-time
watch -n 1 nvidia-smi

# GPU info (utilization + memory)
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
```

## License

Private project - Not licensed for distribution

## References

- [Ollama Documentation](https://ollama.ai/docs)
- [Ollama Python SDK](https://github.com/ollama/ollama-python)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Vue.js Documentation](https://vuejs.org/)
