from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LinkRef:
    source_note: str
    kind: str
    raw: str
    target: str
    line: int
    is_external: bool = False
    resolved_note: str | None = None
    resolved_attachment: str | None = None


@dataclass(slots=True)
class NoteRecord:
    abs_path: Path
    rel_path: str
    title: str
    content: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    wikilinks: list[LinkRef] = field(default_factory=list)
    embeds: list[LinkRef] = field(default_factory=list)
    markdown_links: list[LinkRef] = field(default_factory=list)
    out_note_links: set[str] = field(default_factory=set)
    out_attachment_links: set[str] = field(default_factory=set)
    in_note_links: set[str] = field(default_factory=set)
    is_daily: bool = False
    daily_date: date | None = None


@dataclass(slots=True)
class AttachmentRecord:
    abs_path: Path
    rel_path: str
    filename: str
    extension: str
    size_bytes: int
    referenced_by: set[str] = field(default_factory=set)


@dataclass(slots=True)
class VaultIndex:
    vault_path: Path
    notes: dict[str, NoteRecord] = field(default_factory=dict)
    attachments: dict[str, AttachmentRecord] = field(default_factory=dict)
    all_files: dict[str, int] = field(default_factory=dict)
    note_name_index: dict[str, set[str]] = field(default_factory=dict)
    file_name_index: dict[str, set[str]] = field(default_factory=dict)
    daily_notes_sorted: list[str] = field(default_factory=list)

    def iter_note_links(self):
        for note in self.notes.values():
            for link in note.wikilinks:
                yield note, link
            for link in note.markdown_links:
                yield note, link
            for link in note.embeds:
                yield note, link
