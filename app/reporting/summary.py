from __future__ import annotations

from collections import Counter

from app.models.report import Problem


def build_summary(problems: list[Problem]) -> dict:
    by_category = Counter(problem.category for problem in problems)
    by_severity = Counter(problem.severity for problem in problems)
    by_confidence = Counter(problem.confidence for problem in problems)

    return {
        "total_problems": len(problems),
        "by_category": dict(sorted(by_category.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "by_confidence": dict(sorted(by_confidence.items())),
    }
