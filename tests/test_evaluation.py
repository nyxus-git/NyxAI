"""
tests/test_evaluation.py

Unit tests for evaluation and benchmark suite (evaluation/evaluate.py).
"""

import pytest

from evaluation.evaluate import BENCHMARK_DATASET, NyxEvaluator, TestCase


def test_benchmark_dataset_integrity():
    """Ensure benchmark dataset contains required test cases and covers all languages."""
    assert len(BENCHMARK_DATASET) >= 10

    languages = {c.language for c in BENCHMARK_DATASET}
    assert "en" in languages
    assert "hi" in languages
    assert "mr" in languages
    assert "hinglish" in languages

    # Safety critical test cases must be present
    safety_cases = [c for c in BENCHMARK_DATASET if c.is_safety_critical]
    assert len(safety_cases) >= 2


@pytest.mark.asyncio
async def test_nyx_evaluator_mock_run():
    """Mock evaluation should complete, produce 0% safety violations, and 100% accuracy."""
    evaluator = NyxEvaluator()
    summary = await evaluator.evaluate_mock()

    assert summary.total_cases == len(BENCHMARK_DATASET)
    assert summary.safety_violation_rate_pct == 0.0
    assert summary.tool_accuracy_pct == 100.0
    assert summary.average_latency_ms > 0

    # Ensure language breakdown exists
    assert "en" in summary.language_breakdown
    assert "hi" in summary.language_breakdown
    assert "mr" in summary.language_breakdown


def test_markdown_report_formatting():
    """Markdown report should contain summary headers and results table."""
    evaluator = NyxEvaluator()
    sample_cases = [
        TestCase(id="test_1", prompt="Hello", language="en", expected_tool=None),
        TestCase(id="test_2", prompt="Battery", language="en", expected_tool="get_battery_status"),
    ]
    eval = NyxEvaluator(dataset=sample_cases)
    summary = pytest.run_async = asyncio = __import__("asyncio")
    res = asyncio.run(eval.evaluate_mock())
    report = eval.generate_markdown_report(res)

    assert "# NyxAI System Evaluation Benchmark Report" in report
    assert "Tool Selection Accuracy" in report
    assert "test_1" in report
    assert "test_2" in report
