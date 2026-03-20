from __future__ import annotations

import datetime as dt
import posixpath
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from app.config.schema import VaultProfileConfig
from app.indexer.scanner import VaultScanner
from app.models.entities import AttachmentRecord, LinkRef, NoteRecord, VaultIndex
from app.parser.markdown import parse_markdown

EXTERNAL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _normalize_rel_path(path_str: str) -> str:
    normalized = posixpath.normpath(path_str.replace("\\", "/"))
    if normalized == ".":
        return ""
    return normalized.lstrip("/")


def _split_link_target(target: str) -> tuple[str, str | None]:
    if "#" not in target:
        return target, None
    path_part, fragment = target.split("#", 1)
    return path_part, fragment


def _is_external_link(target: str) -> bool:
    value = target.strip()
    if not value:
        return False
    if value.startswith("//"):
        return True
    return bool(EXTERNAL_SCHEME_RE.match(value))


def _safe_join(source_rel: str, target: str) -> str:
    source_dir = PurePosixPath(source_rel).parent.as_posix()
    if target.startswith("/"):
        return _normalize_rel_path(target)
    return _normalize_rel_path(posixpath.join(source_dir, target))


def _build_note_lookup(index: VaultIndex) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = {}
    for rel_path in index.notes.keys():
        key_full = rel_path[:-3].lower() if rel_path.lower().endswith(".md") else rel_path.lower()
        key_name = PurePosixPath(rel_path).stem.lower()
        lookup.setdefault(key_full, set()).add(rel_path)
        lookup.setdefault(key_name, set()).add(rel_path)
    return lookup


def _build_attachment_lookup(index: VaultIndex) -> tuple[dict[str, str], dict[str, set[str]]]:
    by_rel: dict[str, str] = {}
    by_name: dict[str, set[str]] = {}
    for rel_path in index.attachments.keys():
        by_rel[rel_path.lower()] = rel_path
        by_name.setdefault(PurePosixPath(rel_path).name.lower(), set()).add(rel_path)
    return by_rel, by_name


def _resolve_note_target(
    source_rel: str,
    target: str,
    note_lookup: dict[str, set[str]],
) -> str | None:
    decoded = unquote(target.strip())
    if not decoded:
        return None

    path_part, _fragment = _split_link_target(decoded)

    candidate_keys: list[str] = []
    direct = _normalize_rel_path(path_part)
    joined = _safe_join(source_rel, path_part)

    for candidate in [direct, joined]:
        if not candidate:
            continue
        lower_candidate = candidate.lower()
        if lower_candidate.endswith(".md"):
            candidate_keys.append(lower_candidate[:-3])
        candidate_keys.append(lower_candidate)

    basename = PurePosixPath(path_part).stem.lower()
    if basename:
        candidate_keys.append(basename)

    seen: set[str] = set()
    for key in candidate_keys:
        if key in seen:
            continue
        seen.add(key)
        matched = note_lookup.get(key)
        if matched:
            return sorted(matched)[0]

    return None


def _resolve_attachment_target(
    source_rel: str,
    target: str,
    attachment_by_rel: dict[str, str],
    attachment_by_name: dict[str, set[str]],
) -> str | None:
    decoded = unquote(target.strip())
    if not decoded:
        return None

    path_part, _fragment = _split_link_target(decoded)

    direct = _normalize_rel_path(path_part).lower()
    joined = _safe_join(source_rel, path_part).lower()
    basename = PurePosixPath(path_part).name.lower()

    for candidate in [direct, joined]:
        if candidate in attachment_by_rel:
            return attachment_by_rel[candidate]

    if basename:
        matches = attachment_by_name.get(basename)
        if matches:
            return sorted(matches)[0]

    return None


def _infer_daily_date(note_rel_path: str, profile: VaultProfileConfig) -> dt.date | None:
    daily = profile.daily
    if not daily.enabled:
        return None

    rel = note_rel_path
    if daily.folder:
        folder = _normalize_rel_path(daily.folder)
        if folder and not rel.startswith(folder + "/") and rel != folder:
            return None

    stem = Path(note_rel_path).stem
    for fmt in daily.date_formats:
        try:
            return dt.datetime.strptime(stem, fmt).date()
        except ValueError:
            continue
    return None


def build_vault_index(vault_path: Path, profile: VaultProfileConfig) -> VaultIndex:
    scanner = VaultScanner(vault_path=vault_path, profile=profile)
    index = VaultIndex(vault_path=vault_path)

    for abs_path, rel_path in scanner.iter_files():
        file_size = abs_path.stat().st_size
        index.all_files[rel_path] = file_size

        lower_rel = rel_path.lower()
        filename_lower = Path(rel_path).name.lower()
        index.file_name_index.setdefault(filename_lower, set()).add(rel_path)

        if lower_rel.endswith(".md"):
            text = abs_path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_markdown(rel_path, text)
            note = NoteRecord(
                abs_path=abs_path,
                rel_path=rel_path,
                title=Path(rel_path).stem,
                content=parsed.body,
                frontmatter=parsed.frontmatter,
                wikilinks=parsed.wikilinks,
                embeds=parsed.embeds,
                markdown_links=parsed.markdown_links,
            )
            note.daily_date = _infer_daily_date(rel_path, profile)
            note.is_daily = note.daily_date is not None
            index.notes[rel_path] = note
            index.note_name_index.setdefault(Path(rel_path).stem.lower(), set()).add(rel_path)
            continue

        attachment = AttachmentRecord(
            abs_path=abs_path,
            rel_path=rel_path,
            filename=Path(rel_path).name,
            extension=Path(rel_path).suffix.lower(),
            size_bytes=file_size,
        )
        index.attachments[rel_path] = attachment

    note_lookup = _build_note_lookup(index)
    attachment_by_rel, attachment_by_name = _build_attachment_lookup(index)

    for note in index.notes.values():
        for link in list(note.wikilinks) + list(note.embeds):
            if _is_external_link(link.target):
                link.is_external = True
                continue

            note_target = _resolve_note_target(note.rel_path, link.target, note_lookup)
            if note_target:
                link.resolved_note = note_target
                note.out_note_links.add(note_target)
                index.notes[note_target].in_note_links.add(note.rel_path)
                continue

            attachment_target = _resolve_attachment_target(
                note.rel_path,
                link.target,
                attachment_by_rel,
                attachment_by_name,
            )
            if attachment_target:
                link.resolved_attachment = attachment_target
                note.out_attachment_links.add(attachment_target)
                index.attachments[attachment_target].referenced_by.add(note.rel_path)

        for link in note.markdown_links:
            if _is_external_link(link.target):
                link.is_external = True
                continue

            target = link.target.strip()
            if target.startswith("#"):
                link.resolved_note = note.rel_path
                continue

            path_part, _fragment = _split_link_target(target)
            ext = PurePosixPath(path_part).suffix.lower()

            if ext in {"", ".md"}:
                note_target = _resolve_note_target(note.rel_path, target, note_lookup)
                if note_target:
                    link.resolved_note = note_target
                    note.out_note_links.add(note_target)
                    index.notes[note_target].in_note_links.add(note.rel_path)
                    continue

            attachment_target = _resolve_attachment_target(
                note.rel_path,
                target,
                attachment_by_rel,
                attachment_by_name,
            )
            if attachment_target:
                link.resolved_attachment = attachment_target
                note.out_attachment_links.add(attachment_target)
                index.attachments[attachment_target].referenced_by.add(note.rel_path)

    daily_candidates = [note for note in index.notes.values() if note.is_daily and note.daily_date is not None]
    daily_sorted = sorted(daily_candidates, key=lambda n: (n.daily_date, n.rel_path))
    index.daily_notes_sorted = [note.rel_path for note in daily_sorted]

    return index


def unresolved_links(index: VaultIndex, kind: str) -> list[tuple[NoteRecord, LinkRef]]:
    output: list[tuple[NoteRecord, LinkRef]] = []
    for note in index.notes.values():
        if kind == "wikilink":
            links = note.wikilinks
        elif kind == "embed":
            links = note.embeds
        elif kind == "markdown":
            links = note.markdown_links
        else:
            raise ValueError(f"Unsupported link kind: {kind}")

        for link in links:
            if link.is_external:
                continue
            if link.resolved_note is None and link.resolved_attachment is None:
                output.append((note, link))

    return output
