from __future__ import annotations

from pathlib import Path


def run_gui(
    *,
    report_path: Path | None,
    vault_path: Path | None,
    config_path: Path | None,
    profile: str | None,
    host: str,
    port: int,
) -> None:
    raise NotImplementedError("GUI is not implemented yet")
