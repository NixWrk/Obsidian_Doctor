from __future__ import annotations

from app.config.schema import VaultProfileConfig
from app.models.entities import VaultIndex
from app.models.report import Problem
from app.rules.base import RuleContext
from app.rules.builtin_rules import resolve_active_rules


def run_rules(index: VaultIndex, profile: VaultProfileConfig) -> list[Problem]:
    context = RuleContext(index=index, profile=profile)
    problems: list[Problem] = []
    for rule in resolve_active_rules(profile):
        problems.extend(rule.run(context))
    return problems
