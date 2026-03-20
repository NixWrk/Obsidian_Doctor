from __future__ import annotations

import datetime as dt
from pathlib import Path

from app.config.schema import VaultProfileConfig
from app.models.entities import LinkRef, NoteRecord, VaultIndex
from app.rules.engine import run_rules


def _rule_ids(problems: list) -> set[str]:
    return {problem.id.split(":", 1)[0] for problem in problems}


def test_broken_links_are_reported() -> None:
    note_a = NoteRecord(
        abs_path=Path("D:/vault/A.md"),
        rel_path="A.md",
        title="A",
        content="",
        wikilinks=[LinkRef(source_note="A.md", kind="wikilink", raw="[[Missing]]", target="Missing", line=1)],
        embeds=[LinkRef(source_note="A.md", kind="embed", raw="![[missing.png]]", target="missing.png", line=2)],
        markdown_links=[LinkRef(source_note="A.md", kind="markdown", raw="[bad](missing.pdf)", target="missing.pdf", line=3)],
    )

    note_b = NoteRecord(
        abs_path=Path("D:/vault/B.md"),
        rel_path="B.md",
        title="B",
        content="",
    )

    index = VaultIndex(vault_path=Path("D:/vault"), notes={"A.md": note_a, "B.md": note_b})
    profile = VaultProfileConfig(active_rules=["broken_wikilink", "broken_embed", "broken_markdown_link"])

    problems = run_rules(index, profile)
    ids = _rule_ids(problems)

    assert "broken_wikilink" in ids
    assert "broken_embed" in ids
    assert "broken_markdown_link" in ids


def test_duplicate_rules_detect_title_and_content() -> None:
    note_one = NoteRecord(
        abs_path=Path("D:/vault/a/Idea.md"),
        rel_path="a/Idea.md",
        title="Idea",
        content="same",
    )
    note_two = NoteRecord(
        abs_path=Path("D:/vault/b/Idea.md"),
        rel_path="b/Idea.md",
        title="Idea",
        content="same",
    )

    index = VaultIndex(
        vault_path=Path("D:/vault"),
        notes={"a/Idea.md": note_one, "b/Idea.md": note_two},
        note_name_index={"idea": {"a/Idea.md", "b/Idea.md"}},
    )

    profile = VaultProfileConfig(active_rules=["duplicate_note_title", "duplicate_note_content"])
    problems = run_rules(index, profile)

    ids = _rule_ids(problems)
    assert "duplicate_note_title" in ids
    assert "duplicate_note_content" in ids


def test_daily_chain_rule_flags_missing_neighbors() -> None:
    day_1 = NoteRecord(
        abs_path=Path("D:/vault/Daily/2026-03-18.md"),
        rel_path="Daily/2026-03-18.md",
        title="2026-03-18",
        content="",
        is_daily=True,
        daily_date=dt.date(2026, 3, 18),
    )
    day_2 = NoteRecord(
        abs_path=Path("D:/vault/Daily/2026-03-20.md"),
        rel_path="Daily/2026-03-20.md",
        title="2026-03-20",
        content="",
        is_daily=True,
        daily_date=dt.date(2026, 3, 20),
    )

    index = VaultIndex(
        vault_path=Path("D:/vault"),
        notes={day_1.rel_path: day_1, day_2.rel_path: day_2},
        daily_notes_sorted=[day_1.rel_path, day_2.rel_path],
    )

    profile = VaultProfileConfig(active_rules=["daily_chain_gap_or_mislink"])
    profile.daily.folder = "Daily"
    profile.daily.expected_navigation = True

    problems = run_rules(index, profile)
    ids = _rule_ids(problems)
    assert "daily_chain_gap_or_mislink" in ids
