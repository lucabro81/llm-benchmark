"""Tests for run_test.py CLI runner."""

import json
from pathlib import Path

import pytest

from src.refactoring_test import BenchmarkResult


def _make_result(run_number=1, final_score=10.0, tokens_per_sec=185.0, compiles=True):
    return BenchmarkResult(
        model="test", fixture="test", timestamp="2025-01-17T14:23:45",
        run_number=run_number, compiles=compiles, compilation_errors=[],
        compilation_warnings=[], pattern_score=10.0, naming_score=1.0,
        final_score=final_score, tokens_per_sec=tokens_per_sec, duration_sec=4.0,
        output_code="code", errors=[],
    )


class TestRunTestSummary:
    """Test summary statistics computed over multiple runs."""

    def test_average_score(self):
        """Should compute correct mean final_score across runs."""
        results = [_make_result(final_score=s) for s in [10.0, 9.0, 8.0]]
        avg = sum(r.final_score for r in results) / len(results)
        assert avg == 9.0

    def test_average_speed(self):
        """Should compute correct mean tokens/sec across runs."""
        results = [_make_result(tokens_per_sec=s) for s in [185.0, 178.0, 182.0]]
        avg = sum(r.tokens_per_sec for r in results) / len(results)
        assert abs(avg - 181.67) < 0.1

    def test_compilation_success_rate(self):
        """Should compute correct fraction of runs that compiled."""
        results = [_make_result(compiles=c) for c in [True, True, False]]
        rate = sum(1 for r in results if r.compiles) / len(results)
        assert abs(rate - 0.667) < 0.01


class TestRunTestOutput:
    """Test JSON serialisation of results."""

    def test_result_serialises_to_json(self):
        """BenchmarkResult.__dict__ should be JSON-serialisable with correct values."""
        result = _make_result(run_number=1, final_score=10.0)
        parsed = json.loads(json.dumps([result.__dict__]))

        assert len(parsed) == 1
        assert parsed[0]["model"] == "test"
        assert parsed[0]["final_score"] == 10.0
        assert parsed[0]["run_number"] == 1
