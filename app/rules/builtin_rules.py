from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from app.config.schema import VaultProfileConfig
from app.indexer.builder import unresolved_links
from app.models.entities import AttachmentRecord, NoteRecord, VaultIndex
from app.models.report import ProblemObject
from app.rules.base import BaseRule, RuleContext

WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
PORTABILITY_FORBIDDEN_CHARS = set('<>:"/\\|?*')
STYLE_KEBAB = "kebab-case"
STYLE_SNAKE = "snake_case"
STYLE_TITLE = "Title Case"
STYLE_OTHER = "mixed/other"


def _normalize_text_for_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines = [line.strip() for line in normalized.split("\n")]
    return "\n".join(cleaned_lines).strip()


def _hash_text(text: str) -> str:
    return hashlib.sha256(_normalize_text_for_hash(text).encode("utf-8")).hexdigest()


def _classify_name_style(name: str) -> str:
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return STYLE_KEBAB
    if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", name):
        return STYLE_SNAKE
    if re.fullmatch(r"[A-Z][A-Za-z0-9]*(?: [A-Z][A-Za-z0-9]*)+", name):
        return STYLE_TITLE
    return STYLE_OTHER


def _portable_filename_issues(filename: str) -> list[str]:
    issues: list[str] = []
    stem = PurePosixPath(filename).stem.lower()
    if stem in WINDOWS_RESERVED_NAMES:
        issues.append("windows_reserved_name")
    if any(char in PORTABILITY_FORBIDDEN_CHARS for char in filename):
        issues.append("forbidden_character")
    if any(ord(char) < 32 for char in filename):
        issues.append("control_character")
    if filename.endswith(" ") or filename.endswith("."):
        issues.append("trailing_space_or_dot")
    return issues


def _canonical_ext(ext_or_type: str) -> str:
    value = ext_or_type.strip().lower()
    if not value:
        return value
    return value if value.startswith(".") else f".{value}"


class BrokenWikiLinkRule(BaseRule):
    rule_id = "broken_wikilink"
    category = "link_integrity"
    severity = "error"

    def run(self, context: RuleContext):
        problems = []
        for note, link in unresolved_links(context.index, "wikilink"):
            problems.append(
                self._problem(
                    title="Broken wikilink",
                    description="Wikilink target does not resolve to existing note or attachment.",
                    objects=[ProblemObject(path=note.rel_path, line=link.line)],
                    evidence={"raw": link.raw, "target": link.target},
                    suggested_actions=[
                        "Create missing note/file or rename the link target.",
                        "If link is obsolete, remove or replace it.",
                    ],
                )
            )
        return problems


class BrokenMarkdownLinkRule(BaseRule):
    rule_id = "broken_markdown_link"
    category = "link_integrity"
    severity = "error"

    def run(self, context: RuleContext):
        problems = []
        for note, link in unresolved_links(context.index, "markdown"):
            problems.append(
                self._problem(
                    title="Broken markdown link",
                    description="Markdown link target does not resolve to existing local object.",
                    objects=[ProblemObject(path=note.rel_path, line=link.line)],
                    evidence={"raw": link.raw, "target": link.target},
                    suggested_actions=[
                        "Fix relative path or rename target file.",
                        "Replace with external URL if this should be external link.",
                    ],
                )
            )
        return problems


class BrokenEmbedRule(BaseRule):
    rule_id = "broken_embed"
    category = "link_integrity"
    severity = "error"

    def run(self, context: RuleContext):
        problems = []
        for note, link in unresolved_links(context.index, "embed"):
            problems.append(
                self._problem(
                    title="Broken embed",
                    description="Embedded object is missing.",
                    objects=[ProblemObject(path=note.rel_path, line=link.line)],
                    evidence={"raw": link.raw, "target": link.target},
                    suggested_actions=[
                        "Restore embedded file or update embed path.",
                    ],
                )
            )
        return problems


class OrphanNoteRule(BaseRule):
    rule_id = "orphan_note"
    category = "connectivity"
    severity = "warning"

    def run(self, context: RuleContext):
        problems = []
        for note in context.index.notes.values():
            if len(note.in_note_links) == 0:
                problems.append(
                    self._problem(
                        title="Orphan note",
                        description="Note has no inbound links from other notes.",
                        objects=[ProblemObject(path=note.rel_path)],
                        evidence={"inbound_count": 0},
                        suggested_actions=[
                            "Add at least one incoming link from related note.",
                        ],
                        confidence="medium",
                    )
                )
        return problems


class NoteWithoutOutboundLinksRule(BaseRule):
    rule_id = "note_without_outbound_links"
    category = "connectivity"
    severity = "info"

    def run(self, context: RuleContext):
        problems = []
        for note in context.index.notes.values():
            if len(note.out_note_links) == 0:
                problems.append(
                    self._problem(
                        title="Note without outbound links",
                        description="Note does not point to other notes.",
                        objects=[ProblemObject(path=note.rel_path)],
                        evidence={"outbound_count": 0},
                        suggested_actions=["Consider linking related concepts from this note."],
                        confidence="medium",
                    )
                )
        return problems


class UnusedAttachmentRule(BaseRule):
    rule_id = "unused_attachment"
    category = "attachments"
    severity = "warning"

    def run(self, context: RuleContext):
        problems = []
        for attachment in context.index.attachments.values():
            if len(attachment.referenced_by) == 0:
                problems.append(
                    self._problem(
                        title="Unused attachment",
                        description="Attachment is not referenced by any note.",
                        objects=[ProblemObject(path=attachment.rel_path)],
                        evidence={"referenced_by_count": 0},
                        suggested_actions=[
                            "Confirm this file is obsolete before deletion.",
                            "If needed, add explicit reference from related note.",
                        ],
                    )
                )
        return problems


class DuplicateNoteTitleRule(BaseRule):
    rule_id = "duplicate_note_title"
    category = "duplicates"
    severity = "warning"

    def run(self, context: RuleContext):
        problems = []
        for title, paths in sorted(context.index.note_name_index.items()):
            if len(paths) <= 1:
                continue
            sorted_paths = sorted(paths)
            problems.append(
                self._problem(
                    title="Duplicate note title",
                    description="Multiple notes share the same title (basename).",
                    objects=[ProblemObject(path=path) for path in sorted_paths],
                    evidence={"title": title, "count": len(sorted_paths)},
                    suggested_actions=[
                        "Decide whether notes should be merged or renamed.",
                    ],
                )
            )
        return problems


class DuplicateNoteContentRule(BaseRule):
    rule_id = "duplicate_note_content"
    category = "duplicates"
    severity = "warning"

    def run(self, context: RuleContext):
        groups: dict[str, list[NoteRecord]] = defaultdict(list)
        for note in context.index.notes.values():
            groups[_hash_text(note.content)].append(note)

        problems = []
        for content_hash, notes in groups.items():
            if len(notes) <= 1:
                continue
            sorted_notes = sorted(notes, key=lambda item: item.rel_path)
            problems.append(
                self._problem(
                    title="Duplicate note content",
                    description="Notes have identical normalized content hash.",
                    objects=[ProblemObject(path=note.rel_path) for note in sorted_notes],
                    evidence={"hash": content_hash, "count": len(sorted_notes)},
                    suggested_actions=[
                        "Review duplicates and merge or archive redundant copies.",
                    ],
                    confidence="high",
                )
            )
        return problems


class DuplicateFilenameRule(BaseRule):
    rule_id = "duplicate_filename"
    category = "duplicates"
    severity = "warning"

    def run(self, context: RuleContext):
        problems = []
        for filename, paths in sorted(context.index.file_name_index.items()):
            if len(paths) <= 1:
                continue
            sorted_paths = sorted(paths)
            problems.append(
                self._problem(
                    title="Duplicate filename",
                    description="Same filename appears in multiple paths.",
                    objects=[ProblemObject(path=path) for path in sorted_paths],
                    evidence={"filename": filename, "count": len(sorted_paths)},
                    suggested_actions=[
                        "Adopt stable naming policy and remove accidental duplicates.",
                    ],
                )
            )
        return problems


class AttachmentNameCollisionRule(BaseRule):
    rule_id = "attachment_name_collision"
    category = "attachments"
    severity = "warning"

    def run(self, context: RuleContext):
        grouped: dict[str, list[AttachmentRecord]] = defaultdict(list)
        for attachment in context.index.attachments.values():
            grouped[attachment.filename.lower()].append(attachment)

        problems = []
        for filename, group in sorted(grouped.items()):
            if len(group) <= 1:
                continue
            sorted_group = sorted(group, key=lambda item: item.rel_path)
            problems.append(
                self._problem(
                    title="Attachment name collision",
                    description="Several attachments share the same name.",
                    objects=[ProblemObject(path=item.rel_path) for item in sorted_group],
                    evidence={"filename": filename, "count": len(sorted_group)},
                    suggested_actions=[
                        "Rename attachments to deterministic names and rewrite links safely.",
                    ],
                )
            )
        return problems


class NonPortableFilenameRule(BaseRule):
    rule_id = "non_portable_filename"
    category = "structural_policy"
    severity = "warning"

    def run(self, context: RuleContext):
        problems = []
        for rel_path in sorted(context.index.all_files.keys()):
            filename = PurePosixPath(rel_path).name
            issues = _portable_filename_issues(filename)
            if not issues:
                continue
            problems.append(
                self._problem(
                    title="Non-portable filename",
                    description="Filename may break portability between operating systems.",
                    objects=[ProblemObject(path=rel_path)],
                    evidence={"filename": filename, "issues": issues},
                    suggested_actions=[
                        "Rename file using portable characters and stable naming convention.",
                    ],
                )
            )
        return problems


class MixedNamingConventionRule(BaseRule):
    rule_id = "mixed_naming_convention"
    category = "structural_policy"
    severity = "info"

    def run(self, context: RuleContext):
        naming = context.profile.naming
        if not naming.enabled:
            return []

        sample_paths_by_style: dict[str, list[str]] = defaultdict(list)
        style_counts: Counter[str] = Counter()
        total = 0

        def consume(name: str, path: str) -> None:
            nonlocal total
            style = _classify_name_style(name)
            style_counts[style] += 1
            total += 1
            if len(sample_paths_by_style[style]) < 5:
                sample_paths_by_style[style].append(path)

        if naming.include_notes:
            for note in context.index.notes.values():
                consume(PurePosixPath(note.rel_path).stem, note.rel_path)

        if naming.include_attachments:
            for attachment in context.index.attachments.values():
                consume(PurePosixPath(attachment.rel_path).stem, attachment.rel_path)

        if total == 0:
            return []

        significant_styles: list[str] = []
        for style in [STYLE_KEBAB, STYLE_SNAKE, STYLE_TITLE]:
            count = style_counts[style]
            ratio = count / total
            if count >= naming.min_count_per_style and ratio >= naming.ratio_threshold:
                significant_styles.append(style)

        if len(significant_styles) < 2:
            return []

        return [
            self._problem(
                title="Mixed naming convention",
                description="Vault contains several significant naming styles.",
                objects=[ProblemObject(path=path) for style in significant_styles for path in sample_paths_by_style[style]],
                evidence={
                    "style_counts": dict(style_counts),
                    "significant_styles": significant_styles,
                    "total": total,
                },
                suggested_actions=[
                    "Choose one naming convention per vault/profile.",
                    "Normalize gradually with preview and manual confirmation.",
                ],
                confidence="medium",
            )
        ]


class UnresolvedTemplateArtifactRule(BaseRule):
    rule_id = "unresolved_template_artifact"
    category = "structural_policy"
    severity = "info"

    def run(self, context: RuleContext):
        template = context.profile.template
        if not template.enabled:
            return []

        compiled_patterns = [(pattern, re.compile(pattern)) for pattern in template.patterns]
        problems = []

        for note in context.index.notes.values():
            matches: list[dict] = []
            for line_number, line in enumerate(note.content.splitlines(), start=1):
                for pattern_text, pattern in compiled_patterns:
                    if pattern.search(line):
                        matches.append({"line": line_number, "pattern": pattern_text, "snippet": line.strip()[:200]})

            if not matches:
                continue

            problems.append(
                self._problem(
                    title="Unresolved template artifact",
                    description="Template marker/token found in note content.",
                    objects=[ProblemObject(path=note.rel_path, line=match["line"]) for match in matches[:20]],
                    evidence={"matches": matches[:50], "match_count": len(matches)},
                    suggested_actions=[
                        "Resolve or remove stale template placeholders.",
                    ],
                )
            )

        return problems


class DailyChainGapOrMislinkRule(BaseRule):
    rule_id = "daily_chain_gap_or_mislink"
    category = "daily_notes"
    severity = "warning"

    def run(self, context: RuleContext):
        if not context.profile.daily.enabled:
            return []

        index = context.index
        daily_notes = [index.notes[path] for path in index.daily_notes_sorted if path in index.notes]
        if len(daily_notes) < 2:
            return []

        problems = []

        for idx, note in enumerate(daily_notes):
            expected_prev = daily_notes[idx - 1].rel_path if idx > 0 else None
            expected_next = daily_notes[idx + 1].rel_path if idx + 1 < len(daily_notes) else None

            linked_daily = [
                index.notes[target]
                for target in note.out_note_links
                if target in index.notes and index.notes[target].is_daily and index.notes[target].daily_date is not None
            ]

            linked_prev = None
            linked_next = None
            if note.daily_date is not None:
                earlier = [item for item in linked_daily if item.daily_date and item.daily_date < note.daily_date]
                later = [item for item in linked_daily if item.daily_date and item.daily_date > note.daily_date]
                if earlier:
                    linked_prev = max(earlier, key=lambda item: item.daily_date).rel_path
                if later:
                    linked_next = min(later, key=lambda item: item.daily_date).rel_path

            issue_codes: list[str] = []

            if expected_prev and linked_prev and linked_prev != expected_prev:
                issue_codes.append("mislinked_previous")
            if expected_next and linked_next and linked_next != expected_next:
                issue_codes.append("mislinked_next")

            if context.profile.daily.expected_navigation:
                if expected_prev and linked_prev is None:
                    issue_codes.append("missing_previous")
                if expected_next and linked_next is None:
                    issue_codes.append("missing_next")

            if not issue_codes:
                continue

            problems.append(
                self._problem(
                    title="Daily chain gap or mislink",
                    description="Daily note navigation does not match previous/next existing daily neighbors.",
                    objects=[ProblemObject(path=note.rel_path)],
                    evidence={
                        "issues": issue_codes,
                        "expected_prev": expected_prev,
                        "expected_next": expected_next,
                        "linked_prev": linked_prev,
                        "linked_next": linked_next,
                    },
                    suggested_actions=[
                        "Update previous/next links to point to real existing daily neighbors.",
                    ],
                    confidence="medium",
                )
            )

        return problems


class LargeFileThresholdRule(BaseRule):
    rule_id = "large_file_threshold"
    category = "vault_policy"
    severity = "info"

    def run(self, context: RuleContext):
        threshold = context.profile.large_file_threshold_bytes
        problems = []
        for attachment in context.index.attachments.values():
            if attachment.size_bytes <= threshold:
                continue
            problems.append(
                self._problem(
                    title="File exceeds configured size threshold",
                    description="File size is above policy threshold.",
                    objects=[ProblemObject(path=attachment.rel_path)],
                    evidence={
                        "size_bytes": attachment.size_bytes,
                        "threshold_bytes": threshold,
                    },
                    suggested_actions=[
                        "Consider externalizing large binaries or compressing media.",
                    ],
                )
            )
        return problems


class VaultPolicyForbiddenFiletypeRule(BaseRule):
    rule_id = "vault_policy_forbidden_filetype"
    category = "vault_policy"
    severity = "warning"

    def run(self, context: RuleContext):
        forbidden = {_canonical_ext(item) for item in context.profile.forbidden_filetypes if item}
        if not forbidden:
            return []

        problems = []
        for rel_path in sorted(context.index.all_files.keys()):
            ext = PurePosixPath(rel_path).suffix.lower()
            if ext not in forbidden:
                continue
            problems.append(
                self._problem(
                    title="Forbidden filetype detected",
                    description="File extension is forbidden by current vault profile.",
                    objects=[ProblemObject(path=rel_path)],
                    evidence={"extension": ext, "forbidden": sorted(forbidden)},
                    suggested_actions=[
                        "Move file outside vault or switch to allowed format.",
                    ],
                )
            )
        return problems


BUILTIN_RULES: dict[str, type[BaseRule]] = {
    rule.rule_id: rule
    for rule in [
        BrokenWikiLinkRule,
        BrokenMarkdownLinkRule,
        BrokenEmbedRule,
        OrphanNoteRule,
        NoteWithoutOutboundLinksRule,
        UnusedAttachmentRule,
        DuplicateNoteTitleRule,
        DuplicateNoteContentRule,
        DuplicateFilenameRule,
        AttachmentNameCollisionRule,
        NonPortableFilenameRule,
        MixedNamingConventionRule,
        UnresolvedTemplateArtifactRule,
        DailyChainGapOrMislinkRule,
        LargeFileThresholdRule,
        VaultPolicyForbiddenFiletypeRule,
    ]
}


def resolve_active_rules(profile: VaultProfileConfig) -> list[BaseRule]:
    if not profile.active_rules:
        return [rule_type() for rule_type in BUILTIN_RULES.values()]

    active: list[BaseRule] = []
    missing: list[str] = []
    for rule_id in profile.active_rules:
        rule_type = BUILTIN_RULES.get(rule_id)
        if rule_type is None:
            missing.append(rule_id)
            continue
        active.append(rule_type())

    if missing:
        missing_str = ", ".join(missing)
        raise KeyError(f"Unknown rule IDs in config: {missing_str}")

    return active
