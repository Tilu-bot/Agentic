"""
Agentic - Task orchestration
=============================
Classifier + router + lightweight quality gate used by Cortex.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.skill_registry import SkillSpec
from utils.config import cfg

_CODING_RE = re.compile(
    r"\b(code|bug|debug|fix|refactor|pytest|test|stack\s*trace|exception|function|class)\b",
    re.IGNORECASE,
)
_RESEARCH_RE = re.compile(
    r"(latest|today|news|research|analy[sz]e|compare|source|web|internet|current)",
    re.IGNORECASE,
)
_DATA_RE = re.compile(
    r"(extract|parse|summari[sz]e|csv|xlsx|docx|pdf|table|dataset)",
    re.IGNORECASE,
)
_RISKY_RE = re.compile(
    r"(delete|drop|remove|overwrite|reset|deploy|prod|production|credential|secret)",
    re.IGNORECASE,
)
_LONG_RE = re.compile(
    r"(end\s*to\s*end|full\s*workflow|long\s*task|continuous|all\s*steps)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TaskPlan:
    task_kind: str
    reason: str
    model_candidates: list[str]
    todo_steps: list[str]
    skill_cards: str
    quality_threshold: float
    long_horizon: bool


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    score: float
    reasons: list[str]


def _split_models(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]


def _threshold_fraction() -> float:
    raw = float(cfg.get("orchestration_quality_threshold", 60))
    if raw > 1.0:
        raw = raw / 100.0
    return max(0.1, min(0.95, raw))


def classify_task(text: str, has_attachments: bool = False) -> tuple[str, str]:
    lowered = text.strip().lower()
    if _RISKY_RE.search(lowered):
        return "risky_action", "contains destructive or production-sensitive intent"
    if _LONG_RE.search(lowered):
        return "long_workflow", "explicit request for full autonomous workflow"
    if _CODING_RE.search(lowered):
        return "coding", "contains coding/debug/test language"
    if _RESEARCH_RE.search(lowered):
        return "research", "asks for current info/comparison/research"
    if has_attachments or _DATA_RE.search(lowered):
        return "data_extraction", "attachment/data parsing intent detected"
    return "general", "default general assistant request"


def _todo_for_kind(kind: str, text: str) -> list[str]:
    if not cfg.get("orchestration_todo_enabled", True):
        return []
    if kind == "coding":
        return [
            "Inspect relevant files and runtime context",
            "Implement minimal safe code changes",
            "Run validation checks and summarize results",
        ]
    if kind == "research":
        return [
            "Collect sources from multiple domains",
            "Extract concrete facts with dates",
            "Synthesize answer with citations and caveats",
        ]
    if kind == "data_extraction":
        return [
            "Read and normalize attachment/content",
            "Extract requested fields and verify consistency",
            "Return concise structured output",
        ]
    if kind in ("long_workflow", "risky_action"):
        return [
            "Plan steps with checkpoints and rollback awareness",
            "Execute tasks in small verifiable batches",
            "Run final quality checks before completion",
        ]
    return [
        "Understand request and constraints",
        "Execute required actions",
        "Validate result and provide concise answer",
    ]


def _score_skill(spec: SkillSpec, query_terms: set[str]) -> float:
    hay = " ".join([
        spec.name,
        spec.description,
        " ".join(spec.tags),
        " ".join(spec.parameters.keys()),
    ]).lower()
    if not hay.strip():
        return 0.0
    score = 0.0
    for term in query_terms:
        if term and term in hay:
            score += 1.0
    if "web" in spec.name or "search" in spec.name:
        score += 0.2
    if "file" in spec.name or "doc" in spec.name:
        score += 0.2
    return score


def build_skill_cards(query: str, specs: list[SkillSpec]) -> str:
    if not cfg.get("orchestration_skill_cards_enabled", True):
        return ""
    max_cards = int(cfg.get("orchestration_skill_card_limit", 5))
    terms = {w for w in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(w) > 2}
    scored = sorted(
        ((spec, _score_skill(spec, terms)) for spec in specs),
        key=lambda pair: pair[1],
        reverse=True,
    )
    selected = [spec for spec, score in scored if score > 0][:max_cards]
    if not selected:
        return ""

    lines: list[str] = ["== Relevant Skill Cards =="]
    for spec in selected:
        req = ", ".join(spec.required) if spec.required else "none"
        params = ", ".join(spec.parameters.keys()) if spec.parameters else "none"
        lines.append(f"- {spec.name}: {spec.description}")
        lines.append(f"  required={req}; params={params}")
    return "\n".join(lines)


def route_models(task_kind: str, current_model: str) -> list[str]:
    fast = cfg.get("orchestration_fast_model_id", current_model)
    code = cfg.get("orchestration_code_model_id", current_model)
    research = cfg.get("orchestration_research_model_id", current_model)
    longrun = cfg.get("orchestration_longrun_model_id", current_model)
    extra = _split_models(cfg.get("orchestration_fallback_models", ""))

    if task_kind == "coding":
        ladder = [code, fast]
    elif task_kind == "research":
        ladder = [research, code, fast]
    elif task_kind in ("long_workflow", "risky_action"):
        ladder = [longrun, research, code, fast]
    else:
        ladder = [fast, code]

    ladder.extend(extra)
    deduped: list[str] = []
    seen: set[str] = set()
    for model_id in ladder:
        cleaned = (model_id or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped or [current_model]


def build_plan(query: str, specs: list[SkillSpec], current_model: str, has_attachments: bool = False) -> TaskPlan:
    task_kind, reason = classify_task(query, has_attachments=has_attachments)
    models = route_models(task_kind, current_model)
    todo_steps = _todo_for_kind(task_kind, query)
    skill_cards = build_skill_cards(query, specs)
    threshold = _threshold_fraction()
    return TaskPlan(
        task_kind=task_kind,
        reason=reason,
        model_candidates=models,
        todo_steps=todo_steps,
        skill_cards=skill_cards,
        quality_threshold=max(0.1, min(0.95, threshold)),
        long_horizon=task_kind in ("long_workflow", "risky_action"),
    )


def quality_gate(response: str, query: str, tool_calls: int, skill_failures: int) -> QualityGateResult:
    reasons: list[str] = []
    score = 1.0
    text = (response or "").strip()

    if len(text) < 40:
        score -= 0.45
        reasons.append("response too short")
    if "@@SKILL:" in text or "<tool_call>" in text or "<skill_call>" in text:
        score -= 0.4
        reasons.append("contains unresolved tool-call markers")
    if "i cannot access" in text.lower() and _RESEARCH_RE.search(query):
        score -= 0.3
        reasons.append("claims no access despite research-like query")
    if tool_calls > 0 and skill_failures > 0 and (skill_failures / tool_calls) >= 0.5:
        score -= 0.25
        reasons.append("high skill failure ratio")

    score = max(0.0, min(1.0, score))
    threshold = _threshold_fraction()
    return QualityGateResult(
        passed=score >= threshold,
        score=score,
        reasons=reasons,
    )


def format_plan_block(plan: TaskPlan) -> str:
    lines = [
        "== Task Route ==",
        f"Task kind: {plan.task_kind}",
        f"Reason: {plan.reason}",
        f"Model ladder: {', '.join(plan.model_candidates)}",
    ]
    if plan.todo_steps:
        lines.append("== Todo Plan ==")
        for idx, step in enumerate(plan.todo_steps, start=1):
            lines.append(f"{idx}. {step}")
    if plan.skill_cards:
        lines.append(plan.skill_cards)
    lines.append(
        "Execute the plan, keep progress explicit, and prioritize verified outcomes over speculation."
    )
    return "\n".join(lines)
