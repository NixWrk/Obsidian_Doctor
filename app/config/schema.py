from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_TEMPLATE_PATTERNS = [
    r"<%[^%]*%>",
    r"\{\{\s*date\s*\}\}",
    r"\{\{\s*title\s*\}\}",
    r"\{\{[^}]+\}\}",
]


@dataclass(slots=True)
class DailyConfig:
    enabled: bool = True
    folder: str | None = None
    date_formats: list[str] = field(default_factory=lambda: ["%Y-%m-%d", "%Y_%m_%d", "%Y.%m.%d"])
    expected_navigation: bool = False


@dataclass(slots=True)
class NamingConventionConfig:
    enabled: bool = True
    min_count_per_style: int = 3
    ratio_threshold: float = 0.15
    include_notes: bool = True
    include_attachments: bool = True


@dataclass(slots=True)
class TemplateArtifactConfig:
    enabled: bool = True
    patterns: list[str] = field(default_factory=lambda: list(DEFAULT_TEMPLATE_PATTERNS))


@dataclass(slots=True)
class VaultProfileConfig:
    name: str = "default"
    exclude_dirs: list[str] = field(default_factory=lambda: [".obsidian", ".git", "__pycache__"])
    exclude_globs: list[str] = field(default_factory=list)
    large_file_threshold_bytes: int = 20 * 1024 * 1024
    forbidden_filetypes: list[str] = field(default_factory=list)
    daily: DailyConfig = field(default_factory=DailyConfig)
    naming: NamingConventionConfig = field(default_factory=NamingConventionConfig)
    template: TemplateArtifactConfig = field(default_factory=TemplateArtifactConfig)
    active_rules: list[str] | None = None


@dataclass(slots=True)
class AppConfig:
    default_profile: str = "default"
    profiles: dict[str, VaultProfileConfig] = field(default_factory=lambda: {"default": VaultProfileConfig()})

    def get_profile(self, profile_name: str | None = None) -> VaultProfileConfig:
        selected = profile_name or self.default_profile
        if selected not in self.profiles:
            available = ", ".join(sorted(self.profiles))
            raise KeyError(f"Profile '{selected}' not found. Available: {available}")
        return self.profiles[selected]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
