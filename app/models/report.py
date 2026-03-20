from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class ProblemObject:
    path: str
    line: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Problem:
    id: str
    category: str
    severity: str
    confidence: str
    actionability: str
    title: str
    description: str
    objects: list[ProblemObject]
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_actions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScanReport:
    scan_id: str
    tool_version: str
    generated_at: str
    vault: dict[str, Any]
    config: dict[str, Any]
    summary: dict[str, Any]
    problems: list[Problem]

    @classmethod
    def create(
        cls,
        *,
        scan_id: str,
        tool_version: str,
        vault: dict[str, Any],
        config: dict[str, Any],
        summary: dict[str, Any],
        problems: list[Problem],
    ) -> "ScanReport":
        return cls(
            scan_id=scan_id,
            tool_version=tool_version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            vault=vault,
            config=config,
            summary=summary,
            problems=problems,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["problems"] = [asdict(problem) for problem in self.problems]
        return payload
