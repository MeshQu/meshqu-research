"""Arm C handler — density-control + token-parity check.

Arm C is the volume-matched control for E3's L3 decomposition. It adds
prompt content of comparable size and structure to Arm A's L3 precedent
block, but with **no concrete prior cases, no verdicts, and no
compliance-alert tone**. Arm A − Arm C isolates raw volume effects from
the precedent effect (see ``planning/experiment_design.md`` § Piece 1).

## Module layout

The package spec calls for ``meshqu_runner/arms/arm_c.py`` (an ``arms/``
package). Wave 2 of E3 dispatches up to six sibling agents in parallel
working on per-arm handlers; converting the existing ``arms.py`` module
to an ``arms/`` package would collide with every other Wave 2 PR. The
minimum-intervention compromise — same as E3-001's "extend in place,
don't re-shape" posture — is a sibling module ``arm_c.py`` that
registers against the existing ``arms.HANDLERS`` registry. Behaviour is
identical; only the import path differs.

## The static block

Arm C is the only arm that does **not** vary per target record. The
locked content at ``runner/prompts/armC_density_control.md`` (SHA-bound
by the ``v0.3-predictions-locked`` tag, neutrality-reviewed by Sam
pre-lock) is appended verbatim to the L0 baseline. The target record is
accepted for signature parity with Arms A/B but only the L0 baseline
consults it.

## HTML neutrality-contract comment

The locked file begins with an HTML comment block carrying authoring
metadata + the neutrality-contract terms the content was inspected
against pre-lock. That metadata is **not** prompt content — it is for
human inspectors. The Wave-2 dispatch convention (Sam's resolution) is
to **strip leading HTML comments at render time** without mutating the
locked file bytes. ``strip_leading_html_comment_block`` does exactly
this; the locked SHA is verified before/after by the test suite and the
PR body.

## Token-parity check

The locked Arm C block is matched to E2's L3 precedent block on token
count (within ±5%). The parity check renders both prompts over the same
target records (≥5; 10 by default for an extended sample) and emits a
per-record table with ratios. If the realised parity sits outside ±5%,
the package spec requires surfacing the gap to Sam *without* authoring
a top-up — the locked content is SHA-bound and a content edit needs a
fresh tag.

The check uses the same tokenizer the primary agent uses: ``gpt-5.4``
is a GPT-5-family model and ``tiktoken``'s ``o200k_base`` encoding is
the right one for that family. ``gpt-5.4`` is not yet registered in
``tiktoken.encoding_for_model``; we pin ``o200k_base`` explicitly so a
future ``encoding_for_model`` registration cannot silently shift the
parity number.
"""
from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .arms import register
from .eval_loop import build_user_message


# ---------------------------------------------------------------------------
# Locked content
# ---------------------------------------------------------------------------

# Path to the locked Arm C template, relative to this module's package root.
# Resolved against ``Path(__file__).resolve().parent.parent`` so a checkout
# at ``procurement-context-disambiguation/runner/`` resolves correctly.
ARM_C_TEMPLATE_RELATIVE_PATH = Path("prompts") / "armC_density_control.md"
"""Locked density-control content; SHA-bound by v0.3-predictions-locked.

The four ``## Reference N: record-structure note`` sections are what
gets rendered. The leading HTML comment carries authoring metadata and
the neutrality contract — stripped before rendering."""


# Strip a single leading HTML comment block ``<!-- ... -->`` from the
# locked template, including the trailing blank line(s). DOTALL so the
# comment can span newlines; anchored at the start of the string so we
# can never accidentally remove a comment buried deeper in the file.
_LEADING_HTML_COMMENT_RE = re.compile(r"^\s*<!--.*?-->\s*\n*", re.DOTALL)


# Section header inserted between the L0 baseline and the locked block.
# Mirrors E2's ``## Precedents from MRP-2026-02`` framing style — a
# single ``##`` marker so the model parses the addition as one
# structural block in the composed user message.
ARM_C_SECTION_HEADER = "## Reference notes"


# Section header E2 emits at L3, retained here so the per-record parity
# helper can render an L3-shaped reference without depending on Arm A's
# (in-flight) handler module.
L3_SECTION_HEADER = "## Precedents from MRP-2026-02"


# Token encoding the primary agent's tokenizer uses.
#
# ``gpt-5.4`` is a GPT-5-family model. Tiktoken does not currently
# auto-map ``gpt-5.4-2026-03-05`` via ``encoding_for_model`` — the
# encoding for the GPT-5 generation is ``o200k_base`` (the same one
# OpenAI uses for GPT-4o and the GPT-5 family). Pinning ``o200k_base``
# explicitly insulates the parity number from any future tiktoken
# registration changes.
PRIMARY_AGENT_TIKTOKEN_ENCODING = "o200k_base"


# Default sample size for the extended parity check. The package spec
# (§2) calls for "10 records, sampled from the corpus deterministically"
# in addition to the 3-record smoke set.
DEFAULT_PARITY_SAMPLE_SIZE = 10


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------


def load_locked_arm_c_template(template_path: Path | None = None) -> str:
    """Read the locked Arm C density-control template verbatim.

    Returns the raw file content **before** the HTML-comment strip —
    callers wanting the rendered form should pipe through
    ``strip_leading_html_comment_block``. Returning the raw bytes lets
    tests verify the locked content hasn't been mutated by comparing
    SHA-256 against the v0.3-tag-bound value."""
    if template_path is None:
        template_path = (
            Path(__file__).resolve().parent.parent
            / ARM_C_TEMPLATE_RELATIVE_PATH
        )
    if not template_path.is_file():
        raise FileNotFoundError(
            f"Locked Arm C template missing: {template_path}. "
            "The file is SHA-bound by v0.3-predictions-locked; this is "
            "a stop condition, not a no-op."
        )
    return template_path.read_text(encoding="utf-8")


def strip_leading_html_comment_block(text: str) -> str:
    """Remove a single leading ``<!-- ... -->`` comment from ``text``.

    Returns ``text`` unchanged when no leading comment is present (e.g.
    the locked file is later re-saved without the inspector header).
    The trailing blank line after the closing ``-->`` is consumed so the
    rendered output begins cleanly at the first ``## Reference 1:``
    header.

    This is the Wave-2 dispatch convention: locked file bytes stay
    untouched on disk (the SHA-bound contract); the comment is stripped
    at render time before sending to the LLM. Sam's resolution after
    the Wave 2 chaos."""
    return _LEADING_HTML_COMMENT_RE.sub("", text, count=1)


def render_arm_c_block(template_path: Path | None = None) -> str:
    """Load + strip the locked Arm C block.

    The returned string is the post-strip content the LLM actually
    sees — this is what the token-parity check measures (per the
    redispatch protocol)."""
    raw = load_locked_arm_c_template(template_path)
    return strip_leading_html_comment_block(raw)


def render_arm_c_prompt(
    target_record: Mapping[str, Any],
    *,
    template_path: Path | None = None,
) -> str:
    """Compose Arm C's full rendered prompt for one target record.

    Structure: ``<L0 baseline>\\n\\n## Reference notes\\n\\n<block>``.

    The L0 baseline is the same canonical-JSON user message E2 emits at
    L0: ``{decision_type, fields, substrate_notes}`` sorted-keys
    canonical JSON. Constructed via the inherited
    ``eval_loop.build_user_message`` so the byte sequence matches what
    the primary agent would see in any other arm's L0 contribution."""
    substrate_notes = target_record.get("substrate_notes") or {}
    base_message = build_user_message(
        context=target_record,
        substrate_notes=substrate_notes,
    )
    block = render_arm_c_block(template_path)
    return f"{base_message}\n\n{ARM_C_SECTION_HEADER}\n\n{block}"


# ---------------------------------------------------------------------------
# Registry binding
# ---------------------------------------------------------------------------


@register("arm_c")
def arm_c_handler(record: Mapping[str, Any], **_kwargs: Any) -> str:
    """``arms.HANDLERS["arm_c"]`` entry point.

    Replaces the foundation's placeholder. Accepts arbitrary kwargs
    (the registry filters by signature in ``arms.dispatch``; the
    placeholder pattern is ``**kwargs``-tolerant) — Arm C ignores all
    of them because it adds **static** content. The signature
    parity with Arm A / Arm B (which DO consume helpers like
    ``precedent_selector``) is the only reason ``record`` is named at
    all here."""
    return render_arm_c_prompt(record)


# ---------------------------------------------------------------------------
# Token-parity check
# ---------------------------------------------------------------------------


def _get_primary_tokenizer():
    """Return a tiktoken encoding object for the primary agent's
    tokenizer. Imported lazily so the rest of the module imports cleanly
    in environments without tiktoken (e.g. CI with a slimmed dep set
    that needs only the placeholder handlers to function)."""
    try:
        import tiktoken
    except ImportError as e:  # pragma: no cover - exercised by env probes
        raise ImportError(
            "tiktoken is required for the token-parity check. "
            "Install with `pip install tiktoken`. "
            "(Arm C's handler itself does not need tiktoken; only the "
            "parity helper does.)"
        ) from e
    return tiktoken.get_encoding(PRIMARY_AGENT_TIKTOKEN_ENCODING)


def deterministic_sample(
    records: Sequence[Mapping[str, Any]],
    *,
    n: int,
) -> list[Mapping[str, Any]]:
    """Return the lowest-``n`` records by ``sha256(ocid)`` hex sort.

    Same deterministic sampling primitive E3-007 will use for the
    diagnostic subset (see ``e3-007-diagnostic-subset-selector.md``).
    Reused here so the parity-check sample is reproducible across
    Python interpreters and across reruns."""
    keyed = []
    for r in records:
        ocid = r.get("ocid")
        if not isinstance(ocid, str):
            metadata = r.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("ocid"), str):
                ocid = metadata["ocid"]
            else:
                continue  # records without OCIDs aren't sampleable
        keyed.append((hashlib.sha256(ocid.encode("utf-8")).hexdigest(), r))
    keyed.sort(key=lambda pair: pair[0])
    return [r for _, r in keyed[:n]]


@dataclass(frozen=True)
class ParityRecord:
    """Per-record entry in the parity report."""

    ocid: str
    arm_a_tokens: int
    arm_c_tokens: int

    @property
    def ratio(self) -> float:
        """Arm C / Arm A. 1.0 means perfect parity; 0.95-1.05 is the
        design's ±5% band."""
        return self.arm_c_tokens / self.arm_a_tokens

    @property
    def delta_pct(self) -> float:
        """Percentage delta (signed). Negative = Arm C under-volume."""
        return (self.ratio - 1.0) * 100.0


@dataclass(frozen=True)
class ParityReport:
    """Aggregate parity result over ``records``."""

    records: tuple[ParityRecord, ...]

    @property
    def ratios(self) -> tuple[float, ...]:
        return tuple(r.ratio for r in self.records)

    @property
    def mean_ratio(self) -> float:
        if not self.records:
            return 0.0
        return statistics.mean(self.ratios)

    @property
    def min_ratio(self) -> float:
        return min(self.ratios) if self.records else 0.0

    @property
    def max_ratio(self) -> float:
        return max(self.ratios) if self.records else 0.0

    @property
    def within_design_band(self) -> bool:
        """True iff the *mean* ratio sits within the design's ±5%
        band (per ``planning/build_packages/e3-004-...`` §4 test)."""
        return 0.95 <= self.mean_ratio <= 1.05

    def to_markdown_table(self) -> str:
        """Render the per-record table for the PR body. Markdown
        format mirrors how E2's run-manifest tables are quoted in the
        writeup so the analyst's eye doesn't have to re-learn the
        column order."""
        lines = [
            "| OCID | Arm A tokens | Arm C tokens | Ratio (C/A) | Delta % |",
            "|------|-------------:|-------------:|------------:|--------:|",
        ]
        for r in self.records:
            lines.append(
                f"| `{r.ocid}` | {r.arm_a_tokens} | {r.arm_c_tokens} "
                f"| {r.ratio:.4f} | {r.delta_pct:+.2f}% |"
            )
        lines.append(
            f"| **Mean** |  |  | **{self.mean_ratio:.4f}** "
            f"| **{(self.mean_ratio - 1) * 100:+.2f}%** |"
        )
        lines.append(
            f"| **Min**  |  |  | {self.min_ratio:.4f} "
            f"| {(self.min_ratio - 1) * 100:+.2f}% |"
        )
        lines.append(
            f"| **Max**  |  |  | {self.max_ratio:.4f} "
            f"| {(self.max_ratio - 1) * 100:+.2f}% |"
        )
        return "\n".join(lines)


def measure_token_parity(
    target_records: Sequence[Mapping[str, Any]],
    *,
    render_arm_a_prompt: Callable[[Mapping[str, Any]], str],
    template_path: Path | None = None,
    tokenizer: Any = None,
) -> ParityReport:
    """Compare Arm C's rendered prompt against Arm A's over the same
    target records.

    ``render_arm_a_prompt`` is injected (rather than imported from a
    sibling module) so this helper stays decoupled from E3-002's
    Arm A handler — Wave 2 ships Arm A and Arm C in parallel; we
    cannot import E3-002 here. The test suite wires Arm A via an L3
    handler over a real or synthetic precedent archive; the dry-run
    CLI wires the same thing against the canonical frozen archive.

    ``tokenizer`` defaults to ``_get_primary_tokenizer()`` — tests can
    inject a fake encoder with the same ``.encode(text) -> list``
    surface to assert on counting behaviour without a tiktoken
    dependency."""
    if tokenizer is None:
        tokenizer = _get_primary_tokenizer()

    out: list[ParityRecord] = []
    for record in target_records:
        ocid = record.get("ocid")
        if not isinstance(ocid, str):
            metadata = record.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("ocid"), str):
                ocid = metadata["ocid"]
            else:
                ocid = f"(no-ocid)#{id(record)}"

        arm_a_message = render_arm_a_prompt(record)
        arm_c_message = render_arm_c_prompt(record, template_path=template_path)

        out.append(
            ParityRecord(
                ocid=ocid,
                arm_a_tokens=len(tokenizer.encode(arm_a_message)),
                arm_c_tokens=len(tokenizer.encode(arm_c_message)),
            )
        )

    return ParityReport(records=tuple(out))
