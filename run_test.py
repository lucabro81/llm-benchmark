#!/usr/bin/env python3
"""CLI runner for LLM benchmark - Phase 1 (Prompt-Only Baseline).

This script runs the refactoring test benchmark with hardcoded configuration,
executes multiple test runs, displays progress and summaries, and saves results
to JSON format.

Usage:
    python run_test.py

Configuration (hardcoded for MVP):
    MODEL: qwen2.5-coder:7b-instruct-q8_0
    FIXTURE: fixtures/refactoring/simple-component
    RUNS: 3
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from rich.console import Console
from rich.progress import track

from src.refactoring_test import RefactoringTest, BenchmarkResult

# Configuration (hardcoded for MVP)
MODEL = "qwen2.5-coder:7b-instruct-q8_0"
FIXTURE = Path("fixtures/refactoring/simple-component")
RUNS = 3
OUTPUT_DIR = Path("results")

console = Console()


def show_header():
    """Display benchmark header with configuration."""
    console.print("\n[bold cyan]╔════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║  LLM Benchmark MVP - Phase 1 (Prompt-Only) ║[/bold cyan]")
    console.print("[bold cyan]╚════════════════════════════════════════════╝[/bold cyan]\n")

    console.print(f"Model:   [yellow]{MODEL}[/yellow]")
    console.print(f"Fixture: [yellow]{FIXTURE}[/yellow]")
    console.print(f"Runs:    [yellow]{RUNS}[/yellow]\n")


def show_run_summary(result: BenchmarkResult):
    """Display summary for a single test run.

    Args:
        result: BenchmarkResult from a single test run
    """
    compile_icon = "✓" if result.compiles else "✗"
    score_icon = "✓" if result.final_score >= 8.0 else "✗"

    console.print(
        f"{compile_icon} Compile | {score_icon} Score | "
        f"Run {result.run_number}: "
        f"Final={result.final_score:.1f}/10 "
        f"(Pattern={result.pattern_score:.1f}), "
        f"Speed={result.tokens_per_sec:.1f} tok/s, "
        f"GPU={result.gpu_avg_utilization:.0f}%"
    )


def save_results(results: List[BenchmarkResult]) -> Path:
    """Save results to JSON file.

    Args:
        results: List of BenchmarkResult objects from all runs

    Returns:
        Path to saved JSON file
    """
    # Create results directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Generate filename with timestamp
    timestamp = results[0].timestamp.replace(":", "-")
    model_name = MODEL.replace(":", "_").replace(".", "-")
    output_file = OUTPUT_DIR / f"{model_name}_refactoring_{timestamp}.json"

    # Convert dataclasses to dicts and save
    with open(output_file, "w") as f:
        json.dump([r.__dict__ for r in results], f, indent=2)

    return output_file


def show_summary(results: List[BenchmarkResult]):
    """Display summary statistics across all runs.

    Args:
        results: List of BenchmarkResult objects from all runs
    """
    # Calculate statistics
    avg_score = sum(r.final_score for r in results) / len(results)
    avg_speed = sum(r.tokens_per_sec for r in results) / len(results)
    avg_gpu = sum(r.gpu_avg_utilization for r in results) / len(results)
    success_count = sum(1 for r in results if r.compiles)
    success_rate = (success_count / len(results)) * 100

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Avg Score:     {avg_score:.2f}/10")
    console.print(f"  Avg Speed:     {avg_speed:.1f} tok/s")
    console.print(f"  Avg GPU:       {avg_gpu:.1f}%")
    console.print(f"  Success Rate:  {success_rate:.0f}% ({success_count}/{len(results)} compiled)")

    # Warnings
    if avg_gpu < 80:
        console.print(
            f"\n[yellow]⚠ Warning: Average GPU utilization is {avg_gpu:.0f}% (target >80%)[/yellow]"
        )
        console.print("[yellow]  → Check Ollama GPU configuration[/yellow]")

    if avg_score < 7.0:
        console.print(
            f"\n[yellow]⚠ Warning: Average score is {avg_score:.1f}/10 (target ≥7.0)[/yellow]"
        )
        console.print("[yellow]  → Model may need fine-tuning or prompt adjustment[/yellow]")


def main() -> int:
    """Run benchmark and save results.

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    try:
        # Display header
        show_header()

        # Initialize test
        try:
            test = RefactoringTest(model=MODEL, fixture_path=FIXTURE)
        except FileNotFoundError as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            console.print("[yellow]  → Verify fixture exists and has required files[/yellow]")
            return 1

        # Run multiple tests
        results = []
        for i in track(range(RUNS), description="Running tests..."):
            result = test.run(run_number=i + 1)
            results.append(result)
            show_run_summary(result)

        # Save results
        output_file = save_results(results)
        console.print(f"\n[green]✓ Results saved to {output_file}[/green]")

        # Display summary statistics
        show_summary(results)

        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Benchmark interrupted by user[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
