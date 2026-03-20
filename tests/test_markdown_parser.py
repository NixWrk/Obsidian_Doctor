from app.parser.markdown import parse_markdown


def test_parse_markdown_extracts_frontmatter_and_links() -> None:
    text = """---
tags:
  - test
---
[[Note A|alias]]
![[image.png]]
[site](https://example.com)
[file](docs/readme.md)
"""

    parsed = parse_markdown("Inbox/Example.md", text)

    assert parsed.frontmatter.get("tags") == ["test"]
    assert parsed.wikilinks[0].target == "Note A"
    assert parsed.embeds[0].target == "image.png"
    assert parsed.markdown_links[0].target == "https://example.com"
    assert parsed.markdown_links[1].target == "docs/readme.md"


def test_parse_markdown_normalizes_targets() -> None:
    text = "[[Folder/Doc#Section|Alias]]\n![[asset.pdf#page=2]]\n"
    parsed = parse_markdown("A.md", text)

    assert parsed.wikilinks[0].target == "Folder/Doc"
    assert parsed.embeds[0].target == "asset.pdf"
