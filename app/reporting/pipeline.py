from __future__ import annotations

from pathlib import Path


def run_scan_to_file(
    *,
    vault_path: Path,
    config_path: Path | None,
    profile: str | None,
    output_path: Path,
) -> None:
    raise NotImplementedError("Scan pipeline is not implemented yet")
