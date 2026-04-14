"""Tests for core/task_orchestrator.py."""
from core.task_orchestrator import build_plan, classify_task, quality_gate, route_models


def test_classify_coding_task():
    kind, reason = classify_task("Please debug this Python exception in tests")
    assert kind == "coding"
    assert "coding" in reason or "debug" in reason


def test_classify_research_task():
    kind, _ = classify_task("What are the latest AI research updates today?")
    assert kind == "research"


def test_route_models_not_empty_and_deduped():
    models = route_models("coding", "google/gemma-3-1b-it")
    assert len(models) >= 1
    assert len(models) == len(set(models))


def test_build_plan_contains_model_candidates():
    plan = build_plan(
        "Do a full autonomous workflow to compare models",
        specs=[],
        current_model="google/gemma-3-1b-it",
        has_attachments=False,
    )
    assert plan.task_kind in {"long_workflow", "research", "general", "risky_action", "coding", "data_extraction"}
    assert plan.model_candidates


def test_quality_gate_rejects_unresolved_tool_markers():
    gate = quality_gate(
        "@@SKILL:read_file {\"path\":\"a\"}@@",
        query="fix code",
        tool_calls=1,
        skill_failures=0,
    )
    assert gate.passed is False
    assert gate.score < 0.7
