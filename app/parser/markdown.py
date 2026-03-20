from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from app.models.entities import LinkRef

WIKILINK_RE = re.compile(r"(!)?\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")


@dataclass(slots=True)
class ParsedMarkdown:
    frontmatter: dict[str, Any]
    body: str
    wikilinks: list[LinkRef]
    embeds: list[LinkRef]
    markdown_links: list[LinkRef]


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    closing_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_index = i
            break

    if closing_index is None:
        return {}, text

    frontmatter_raw = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :])

    try:
        parsed = yaml.safe_load(frontmatter_raw)
    except yaml.YAMLError:
        return {}, body

    if isinstance(parsed, dict):
        return parsed, body
    return {}, body


def _normalize_obsidian_target(raw_target: str) -> str:
    target = raw_target.strip()
    if "|" in target:
        target = target.split("|", 1)[0].strip()
    if "#" in target:
        target = target.split("#", 1)[0].strip()
    return target


def _normalize_markdown_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">") and len(target) >= 2:
        return target[1:-1].strip()
    return target


def parse_markdown(source_note: str, raw_text: str) -> ParsedMarkdown:
    frontmatter, body = _extract_frontmatter(raw_text)

    wikilinks: list[LinkRef] = []
    embeds: list[LinkRef] = []
    markdown_links: list[LinkRef] = []

    for line_no, line in enumerate(body.splitlines(), start=1):
        for match in WIKILINK_RE.finditer(line):
            is_embed = bool(match.group(1))
            raw = match.group(0)
            raw_target = match.group(2)
            target = _normalize_obsidian_target(raw_target)

            link = LinkRef(
                source_note=source_note,
                kind="embed" if is_embed else "wikilink",
                raw=raw,
                target=target,
                line=line_no,
            )
            if is_embed:
                embeds.append(link)
            else:
                wikilinks.append(link)

        for match in MARKDOWN_LINK_RE.finditer(line):
            raw = match.group(0)
            target = _normalize_markdown_target(match.group(2))
            markdown_links.append(
                LinkRef(
                    source_note=source_note,
                    kind="markdown",
                    raw=raw,
                    target=target,
                    line=line_no,
                )
            )

    return ParsedMarkdown(
        frontmatter=frontmatter,
        body=body,
        wikilinks=wikilinks,
        embeds=embeds,
        markdown_links=markdown_links,
    )
