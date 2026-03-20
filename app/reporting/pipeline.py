from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path

from app import __version__
from app.config.loader import load_app_config
from app.models.report import ScanReport
from app.reporting.io import write_json
from app.reporting.summary import build_summary
from app.indexer.builder import build_vault_index
from app.rules.engine import run_rules


def run_scan(
    *,
    vault_path: Path,
    config_path: Path | None,
    profile: str | None,
) -> ScanReport:
    vault = Path(vault_path).resolve()
    config = load_app_config(config_path)
    selected_profile = config.get_profile(profile)

    index = build_vault_index(vault, selected_profile)
    problems = run_rules(index, selected_profile)
    summary = build_summary(problems)

    vault_meta = {
        "path": str(vault),
        "note_count": len(index.notes),
        "attachment_count": len(index.attachments),
        "file_count": len(index.all_files),
        "daily_note_count": len(index.daily_notes_sorted),
        "profile": selected_profile.name,
    }

    return ScanReport.create(
        scan_id=str(uuid.uuid4()),
        tool_version=__version__,
        vault=vault_meta,
        config={
            "default_profile": config.default_profile,
            "profile": asdict(selected_profile),
        },
        summary=summary,
        problems=problems,
    )


def run_scan_to_file(
    *,
    vault_path: Path,
    config_path: Path | None,
    profile: str | None,
    output_path: Path,
) -> ScanReport:
    report = run_scan(vault_path=vault_path, config_path=config_path, profile=profile)
    write_json(output_path, report.to_dict())
    return report
