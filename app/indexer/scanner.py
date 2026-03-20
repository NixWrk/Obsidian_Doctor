from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from app.config.schema import VaultProfileConfig


class VaultScanner:
    def __init__(self, vault_path: Path, profile: VaultProfileConfig) -> None:
        self.vault_path = vault_path
        self.profile = profile

    def _is_excluded_dir(self, relative_dir: str) -> bool:
        if not relative_dir:
            return False
        parts = relative_dir.split("/")
        if any(part in self.profile.exclude_dirs for part in parts):
            return True
        return any(fnmatch.fnmatch(relative_dir, pattern) for pattern in self.profile.exclude_globs)

    def _is_excluded_file(self, relative_file: str) -> bool:
        if any(fnmatch.fnmatch(relative_file, pattern) for pattern in self.profile.exclude_globs):
            return True
        return any(part in self.profile.exclude_dirs for part in relative_file.split("/"))

    def iter_files(self):
        for root, dirs, files in os.walk(self.vault_path):
            root_path = Path(root)
            rel_dir = root_path.relative_to(self.vault_path).as_posix()

            filtered_dirs: list[str] = []
            for dirname in dirs:
                candidate = f"{rel_dir}/{dirname}" if rel_dir != "." else dirname
                if not self._is_excluded_dir(candidate):
                    filtered_dirs.append(dirname)
            dirs[:] = filtered_dirs

            for filename in files:
                abs_path = root_path / filename
                rel_path = abs_path.relative_to(self.vault_path).as_posix()
                if self._is_excluded_file(rel_path):
                    continue
                yield abs_path, rel_path
