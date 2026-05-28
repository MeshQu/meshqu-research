"""Tests for ``meshqu_runner.prompt_loader`` — focused here on the
leading-HTML-comment strip utility introduced by E3-005 to honour
Sam's 2026-05-28 resolution (locked file bytes stay intact; renderer
strips leading methodological comments before sending the prompt to
the LLM).

The package spec for E3-005 enumerates these cases for the strip
utility — every one is exercised below:

- input with no leading comment → returned unchanged
- single-line comment at the start → stripped (comment + trailing newline)
- multi-line comment at the start → stripped (whole block)
- comment followed by blank lines → stripped together
- comment NOT at the start (e.g. inline mid-document) → preserved
- input is only a leading comment → empty string

Plus an idempotence assertion: running the strip twice produces the
same output as running it once.
"""
from __future__ import annotations

from meshqu_runner.prompt_loader import strip_leading_html_comments


def test_no_leading_comment_returns_unchanged():
    text = "## Policy under evaluation\n\nbody text\n"
    assert strip_leading_html_comments(text) == text


def test_single_line_comment_at_start_stripped():
    text = "<!-- header -->\n## Heading\n"
    assert strip_leading_html_comments(text) == "## Heading\n"


def test_multi_line_comment_at_start_stripped():
    text = (
        "<!--\n"
        "This is a multi-line methodological header.\n"
        "It spans several lines and ends here.\n"
        "-->\n"
        "## Real content\n"
    )
    assert strip_leading_html_comments(text) == "## Real content\n"


def test_comment_followed_by_blank_lines_stripped_together():
    text = (
        "<!-- meta -->\n"
        "\n"
        "\n"
        "## First real line\n"
    )
    assert strip_leading_html_comments(text) == "## First real line\n"


def test_comment_not_at_start_is_preserved():
    """The strip is anchored to the very start of the document. Inline
    comments later in the body must survive — they may be intentional
    annotations beside a rule definition."""
    text = (
        "## Heading\n"
        "\n"
        "Body line 1.\n"
        "<!-- inline annotation, NOT to be stripped -->\n"
        "Body line 2.\n"
    )
    assert strip_leading_html_comments(text) == text


def test_only_leading_comment_returns_empty():
    text = "<!-- nothing else -->\n"
    assert strip_leading_html_comments(text) == ""


def test_strip_is_idempotent_on_already_stripped_text():
    text = "<!-- header -->\n## Heading\n\nBody.\n"
    once = strip_leading_html_comments(text)
    twice = strip_leading_html_comments(once)
    assert once == twice == "## Heading\n\nBody.\n"


def test_strip_is_idempotent_on_comment_free_input():
    text = "## Just a heading\n\nNo comment to strip.\n"
    once = strip_leading_html_comments(text)
    twice = strip_leading_html_comments(once)
    assert once == twice == text


def test_multiple_stacked_leading_comments_stripped():
    """Defensive: a future authoring convention that puts two separate
    comment blocks at the top of a file (e.g. "license header" then
    "methodological header") should be handled too."""
    text = (
        "<!-- license: CC0 -->\n"
        "<!-- methodological header -->\n"
        "## Real content\n"
    )
    assert strip_leading_html_comments(text) == "## Real content\n"


def test_strip_preserves_interpolation_token_in_body():
    """Specific to the L4-without-nudge handler: the
    ``{policy_snapshot_json}`` placeholder must survive the strip
    intact. (The strip only consumes leading comments; the token
    lives well after the leading-comment region.)"""
    text = (
        "<!--\n"
        "Methodological note: nudge excised.\n"
        "-->\n"
        "## Policy\n"
        "\n"
        "```json\n"
        "{policy_snapshot_json}\n"
        "```\n"
    )
    result = strip_leading_html_comments(text)
    assert "{policy_snapshot_json}" in result
    assert result.startswith("## Policy")
