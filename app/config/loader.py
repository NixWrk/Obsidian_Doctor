from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config.schema import (
    AppConfig,
    DailyConfig,
    NamingConventionConfig,
    TemplateArtifactConfig,
    VaultProfileConfig,
)


def _as_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return [str(raw)]


def _load_daily(raw: dict[str, Any] | None) -> DailyConfig:
    data = raw or {}
    return DailyConfig(
        enabled=bool(data.get("enabled", True)),
        folder=data.get("folder"),
        date_formats=_as_list(data.get("date_formats")) or ["%Y-%m-%d", "%Y_%m_%d", "%Y.%m.%d"],
        expected_navigation=bool(data.get("expected_navigation", False)),
    )


def _load_naming(raw: dict[str, Any] | None) -> NamingConventionConfig:
    data = raw or {}
    return NamingConventionConfig(
        enabled=bool(data.get("enabled", True)),
        min_count_per_style=int(data.get("min_count_per_style", 3)),
        ratio_threshold=float(data.get("ratio_threshold", 0.15)),
        include_notes=bool(data.get("include_notes", True)),
        include_attachments=bool(data.get("include_attachments", True)),
    )


def _load_template(raw: dict[str, Any] | None) -> TemplateArtifactConfig:
    data = raw or {}
    patterns = _as_list(data.get("patterns"))
    return TemplateArtifactConfig(
        enabled=bool(data.get("enabled", True)),
        patterns=patterns or TemplateArtifactConfig().patterns,
    )


def _load_profile(name: str, raw: dict[str, Any] | None) -> VaultProfileConfig:
    data = raw or {}
    return VaultProfileConfig(
        name=name,
        exclude_dirs=_as_list(data.get("exclude_dirs")) or VaultProfileConfig().exclude_dirs,
        exclude_globs=_as_list(data.get("exclude_globs")),
        large_file_threshold_bytes=int(data.get("large_file_threshold_bytes", 20 * 1024 * 1024)),
        forbidden_filetypes=_as_list(data.get("forbidden_filetypes")),
        daily=_load_daily(data.get("daily")),
        naming=_load_naming(data.get("naming")),
        template=_load_template(data.get("template")),
        active_rules=_as_list(data.get("active_rules")) or None,
    )


def _load_legacy_single_profile(raw: dict[str, Any]) -> AppConfig:
    profile_data = {
        "exclude_dirs": raw.get("exclude_dirs"),
        "exclude_globs": raw.get("exclude_globs"),
        "large_file_threshold_bytes": raw.get("large_file_threshold_bytes"),
        "forbidden_filetypes": raw.get("forbidden_filetypes"),
        "daily": raw.get("daily"),
        "naming": raw.get("naming"),
        "template": raw.get("template"),
        "active_rules": raw.get("active_rules"),
    }
    profile = _load_profile("default", profile_data)
    return AppConfig(default_profile="default", profiles={"default": profile})


def load_app_config(config_path: Path | None = None) -> AppConfig:
    if config_path is None:
        return AppConfig()

    config_file = Path(config_path)
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    if raw is None:
        return AppConfig()
    if not isinstance(raw, dict):
        raise ValueError("Config must be a YAML object")

    if "profiles" not in raw:
        return _load_legacy_single_profile(raw)

    profiles_raw = raw.get("profiles")
    if not isinstance(profiles_raw, dict) or not profiles_raw:
        raise ValueError("Config 'profiles' must be a non-empty object")

    profiles: dict[str, VaultProfileConfig] = {}
    for profile_name, profile_data in profiles_raw.items():
        if profile_data is not None and not isinstance(profile_data, dict):
            raise ValueError(f"Profile '{profile_name}' must be an object")
        profiles[str(profile_name)] = _load_profile(str(profile_name), profile_data)

    default_profile = str(raw.get("default_profile", next(iter(profiles.keys()))))
    if default_profile not in profiles:
        raise ValueError(f"default_profile '{default_profile}' not found in profiles")

    return AppConfig(default_profile=default_profile, profiles=profiles)
