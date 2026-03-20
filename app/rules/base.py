from __future__ import annotations

from dataclasses import dataclass

from app.config.schema import VaultProfileConfig
from app.models.entities import VaultIndex
from app.models.report import Problem, ProblemObject


@dataclass(slots=True)
class RuleContext:
    index: VaultIndex
    profile: VaultProfileConfig


class BaseRule:
    rule_id = "base_rule"
    category = "general"
    severity = "warning"
    confidence = "high"
    actionability = "manual_confirmation_required"

    def __init__(self) -> None:
        self._counter = 0

    def run(self, context: RuleContext) -> list[Problem]:
        raise NotImplementedError

    def _problem(
        self,
        *,
        title: str,
        description: str,
        objects: list[ProblemObject],
        evidence: dict,
        suggested_actions: list[str] | None = None,
        severity: str | None = None,
        confidence: str | None = None,
        actionability: str | None = None,
    ) -> Problem:
        self._counter += 1
        return Problem(
            id=f"{self.rule_id}:{self._counter}",
            category=self.category,
            severity=severity or self.severity,
            confidence=confidence or self.confidence,
            actionability=actionability or self.actionability,
            title=title,
            description=description,
            objects=objects,
            evidence=evidence,
            suggested_actions=suggested_actions or [],
        )
