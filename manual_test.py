#!/usr/bin/env python3
"""Manual testing CLI for LLM Benchmark Suite.

Interactive command-line interface for testing individual components
and running end-to-end benchmarks manually.
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.gpu_monitor import (
    GPUNotAvailableError,
    check_nvidia_smi_available,
    monitor_gpu_during_inference,
)
from src.ollama_client import (
    ModelNotFoundError,
    OllamaConnectionError,
    chat,
    get_ollama_base_url,
)

console = Console()


def print_header():
    """Print application header."""
    console.print(
        Panel.fit(
            "[bold cyan]LLM Benchmark Suite[/bold cyan]\n"
            "[dim]Manual Testing CLI[/dim]",
            border_style="cyan",
        )
    )


def test_ollama_connection():
    """Test Ollama API connection and list models."""
    console.print("\n[bold yellow]Testing Ollama Connection[/bold yellow]")
    console.print(f"URL: {get_ollama_base_url()}")

    try:
        import ollama

        # List available models
        models = ollama.list()

        if not models or "models" not in models or len(models["models"]) == 0:
            console.print("[red]No models found in Ollama[/red]")
            console.print("Pull a model with: [cyan]ollama pull qwen2.5-coder:7b[/cyan]")
            return False

        # Display models table
        table = Table(title="Available Models")
        table.add_column("Model", style="cyan")
        table.add_column("Size", style="green")
        table.add_column("Modified", style="yellow")

        for model in models["models"]:
            # Model is an object with attributes, not a dict
            name = getattr(model, "name", getattr(model, "model", "unknown"))
            size = getattr(model, "size", 0)
            size_gb = size / (1024**3) if size else 0
            modified = getattr(model, "modified_at", "unknown")

            # Handle datetime object or string
            if hasattr(modified, "strftime"):
                modified = modified.strftime("%Y-%m-%d")
            elif isinstance(modified, str):
                modified = modified[:10]
            else:
                modified = str(modified)[:10]

            table.add_row(name, f"{size_gb:.2f} GB", modified)

        console.print(table)
        console.print("[green]Ollama connection successful![/green]")
        return True

    except Exception as e:
        console.print(f"[red]Failed to connect to Ollama: {e}[/red]")
        console.print("\nTroubleshooting:")
        console.print("1. Check if Ollama is running")
        console.print("2. Verify OLLAMA_BASE_URL in .env")
        console.print("3. Try: [cyan]curl http://localhost:11434/api/tags[/cyan]")
        return False


def test_ollama_inference():
    """Test Ollama inference with a simple prompt."""
    console.print("\n[bold yellow]Testing Ollama Inference[/bold yellow]")

    # Get model from user
    model = Prompt.ask(
        "Enter model name",
        default="qwen2.5-coder:7b-instruct-q8_0",
    )

    prompt = Prompt.ask(
        "Enter prompt",
        default="Say 'Hello from Ollama!' and nothing else",
    )

    console.print(f"\n[dim]Calling {model}...[/dim]")

    try:
        result = chat(model=model, prompt=prompt, timeout=30)

        if result.success:
            console.print("\n[green]Response:[/green]")
            console.print(Panel(result.response_text, border_style="green"))

            # Show metrics
            console.print("\n[bold]Metrics:[/bold]")
            console.print(f"Duration: {result.duration_sec:.2f}s")
            console.print(f"Tokens: {result.tokens_generated}")
            console.print(f"Speed: {result.tokens_per_sec:.1f} tok/s")
            return True
        else:
            console.print(f"[red]Error: {result.error}[/red]")
            return False

    except ModelNotFoundError as e:
        console.print(f"[red]Model not found: {e}[/red]")
        console.print("Pull the model with: [cyan]ollama pull {model}[/cyan]")
        return False

    except OllamaConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        return False

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        return False


def test_gpu_monitoring():
    """Test GPU monitoring capabilities."""
    console.print("\n[bold yellow]Testing GPU Monitoring[/bold yellow]")

    # Check nvidia-smi availability
    if not check_nvidia_smi_available():
        console.print("[red]nvidia-smi is not available[/red]")
        console.print("\nThis machine does not have NVIDIA GPU drivers.")
        console.print("GPU monitoring will be mocked in unit tests.")
        return False

    console.print("[green]nvidia-smi is available[/green]")

    # Run a dummy task while monitoring
    console.print("\n[dim]Running 3-second compute task...[/dim]")

    def dummy_task():
        """Simulate some work."""
        import time

        total = 0
        for i in range(10000000):
            total += i
        time.sleep(3)
        return total

    try:
        metrics = monitor_gpu_during_inference(dummy_task, polling_interval=0.5)

        # Display metrics
        table = Table(title="GPU Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Samples Collected", str(metrics.samples))
        table.add_row("Avg Utilization", f"{metrics.avg_utilization:.1f}%")
        table.add_row("Peak Utilization", f"{metrics.peak_utilization:.1f}%")
        table.add_row("Avg Memory Used", f"{metrics.avg_memory_used:.2f} GB")
        table.add_row("Peak Memory Used", f"{metrics.peak_memory_used:.2f} GB")

        console.print(table)

        # Warning if low utilization
        if metrics.avg_utilization < 50:
            console.print(
                "\n[yellow]Warning: Low GPU utilization. "
                "Make sure Ollama is configured to use GPU.[/yellow]"
            )

        console.print("[green]GPU monitoring successful![/green]")
        return True

    except GPUNotAvailableError as e:
        console.print(f"[red]GPU error: {e}[/red]")
        return False

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        return False


def test_ollama_with_gpu():
    """Test Ollama inference with GPU monitoring."""
    console.print("\n[bold yellow]Testing Ollama + GPU Monitoring[/bold yellow]")

    if not check_nvidia_smi_available():
        console.print("[red]nvidia-smi not available, skipping GPU monitoring[/red]")
        return test_ollama_inference()

    # Get model from user
    model = Prompt.ask(
        "Enter model name",
        default="qwen2.5-coder:7b-instruct-q8_0",
    )

    prompt = Prompt.ask(
        "Enter prompt (longer prompts = better GPU metrics)",
        default="Write a Python function to calculate fibonacci numbers recursively",
    )

    console.print(f"\n[dim]Calling {model} with GPU monitoring...[/dim]")

    try:

        def inference_task():
            return chat(model=model, prompt=prompt, timeout=60)

        # Monitor GPU during inference
        metrics = monitor_gpu_during_inference(inference_task, polling_interval=0.5)

        # Get result from callback (need to modify to return both)
        result = inference_task()

        if result.success:
            console.print("\n[green]Response:[/green]")
            console.print(Panel(result.response_text[:500] + "...", border_style="green"))

            # Show combined metrics
            table = Table(title="Combined Metrics")
            table.add_column("Category", style="cyan")
            table.add_column("Metric", style="yellow")
            table.add_column("Value", style="green")

            table.add_row("Inference", "Duration", f"{result.duration_sec:.2f}s")
            table.add_row("Inference", "Tokens", str(result.tokens_generated))
            table.add_row("Inference", "Speed", f"{result.tokens_per_sec:.1f} tok/s")
            table.add_row("GPU", "Avg Utilization", f"{metrics.avg_utilization:.1f}%")
            table.add_row("GPU", "Peak Utilization", f"{metrics.peak_utilization:.1f}%")
            table.add_row("GPU", "Avg Memory", f"{metrics.avg_memory_used:.2f} GB")
            table.add_row("GPU", "Peak Memory", f"{metrics.peak_memory_used:.2f} GB")
            table.add_row("GPU", "Samples", str(metrics.samples))

            console.print(table)

            # Performance assessment
            if metrics.avg_utilization > 80:
                console.print("\n[green]Excellent GPU utilization![/green]")
            elif metrics.avg_utilization > 50:
                console.print("\n[yellow]Moderate GPU utilization[/yellow]")
            else:
                console.print(
                    "\n[red]Low GPU utilization - check Ollama GPU config[/red]"
                )

            return True

        else:
            console.print(f"[red]Error: {result.error}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return False


def show_menu():
    """Display interactive menu."""
    console.print("\n[bold cyan]Available Tests:[/bold cyan]")
    console.print("1. Test Ollama Connection (list models)")
    console.print("2. Test Ollama Inference (simple prompt)")
    console.print("3. Test GPU Monitoring (dummy task)")
    console.print("4. Test Ollama + GPU (combined)")
    console.print("5. Run All Tests")
    console.print("0. Exit")


def main():
    """Main CLI loop."""
    print_header()

    # Show system info
    console.print(f"\n[dim]Python: {sys.version.split()[0]}[/dim]")
    console.print(f"[dim]Ollama URL: {get_ollama_base_url()}[/dim]")
    console.print(
        f"[dim]GPU Available: {check_nvidia_smi_available()}[/dim]"
    )

    while True:
        show_menu()
        choice = Prompt.ask("\nSelect test", choices=["0", "1", "2", "3", "4", "5"])

        if choice == "0":
            console.print("\n[cyan]Goodbye![/cyan]")
            break

        elif choice == "1":
            test_ollama_connection()

        elif choice == "2":
            test_ollama_inference()

        elif choice == "3":
            test_gpu_monitoring()

        elif choice == "4":
            test_ollama_with_gpu()

        elif choice == "5":
            console.print("\n[bold]Running All Tests[/bold]")
            results = []
            results.append(("Ollama Connection", test_ollama_connection()))
            results.append(("Ollama Inference", test_ollama_inference()))
            results.append(("GPU Monitoring", test_gpu_monitoring()))

            # Summary
            console.print("\n[bold]Test Summary:[/bold]")
            for name, passed in results:
                status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
                console.print(f"{status} {name}")

        if not Confirm.ask("\nRun another test?", default=True):
            console.print("\n[cyan]Goodbye![/cyan]")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        sys.exit(1)
