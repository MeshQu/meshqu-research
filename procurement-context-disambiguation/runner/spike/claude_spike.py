#!/usr/bin/env python3
"""
E3 Claude feasibility spike — mechanics only.

Purpose: confirm the second-model arm is runnable before the pre-registration
lock pins the model. This does NOT collect pre-registered data and does NOT
touch the locked diagnostic subset — it runs E2's verbatim agent scaffold over
THREE THROWAWAY SYNTHETIC RECORDS to answer four mechanical questions:

  1. Which Claude model does the key reach? (pin confirmation)
  2. Does the verbatim E2 scaffold yield a parseable verdict JSON from Claude,
     or does it need an output-parsing shim? (portability — option (b))
  3. temperature=0 behaviour on the pinned model.
  4. Latency + token usage sanity.

KEY FINDING (from the claude-api skill, before running):
  Claude Opus 4.7 (`claude-opus-4-7`) REMOVED the `temperature` parameter —
  sending temperature=0 returns HTTP 400. E2's gpt-5.4 agent ran at temp 0.
  So the cross-model arm cannot match "temp 0" on Opus 4.7. Two options, to be
  decided from this spike's output:
    (A) pin claude-opus-4-7, drop temperature (most capable; determinism via
        effort:low + a tight prompt, not a temp knob)
    (B) pin claude-sonnet-4-6, which still accepts temperature=0 (matches the
        gpt-5.4 temp-0 setting more closely; less capable)
  This harness runs option (A) by default (no temperature) and has a --sonnet
  flag to test option (B) with temperature=0 so the two can be compared.

SCOPE GUARDS:
  - Throwaway synthetic records only. NOT the frozen 283-corpus, NOT the locked
    diagnostic-100 subset. No pre-registered data is read or touched.
  - Read-only against the repo (reads E2's system_prompt.md verbatim).
  - No receipts, no signing, no MeshQu calls. Pure model-mechanics probe.

RUN:
  pip install anthropic
  export ANTHROPIC_API_KEY=sk-ant-...
  python3 claude_spike.py            # option (A): claude-opus-4-7, no temperature
  python3 claude_spike.py --sonnet   # option (B): claude-sonnet-4-6, temperature=0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("anthropic SDK not installed. Run: pip install anthropic")

# E2's verbatim agent scaffold — read from the published E2 runner so the spike
# uses byte-identical instructions to the primary-model run.
E2_SYSTEM_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "procurement-context-gradient"
    / "runner"
    / "system_prompt.md"
)

# Three throwaway synthetic records. Hand-written for the spike; deliberately
# NOT drawn from the frozen corpus. Shapes mirror the substrate fields the real
# records carry, so the scaffold exercises the same reasoning surface.
THROWAWAY_RECORDS = [
    {
        "label": "synthetic-A (clear timing breach)",
        "fields": {
            "contract_value": "£4,200,000",
            "award_method": "open",
            "regime": "PA23 (above threshold)",
            "award_date": "2026-01-10",
            "publication_delay_days": 96,
            "procurement_method_open_flag": True,
            "conflict_of_interest_declaration": "not present in record",
        },
    },
    {
        "label": "synthetic-B (sparse / ambiguous)",
        "fields": {
            "contract_value": "£38,500",
            "award_method": "selective",
            "regime": "PA23 (below threshold)",
            "award_date": "2026-02-22",
            "publication_delay_days": 12,
            "procurement_method_open_flag": False,
            "conflict_of_interest_declaration": "field unavailable on this substrate",
        },
    },
    {
        "label": "synthetic-C (clean, low risk)",
        "fields": {
            "contract_value": "£610,000",
            "award_method": "open",
            "regime": "PCR 2015 (above threshold)",
            "award_date": "2026-03-05",
            "publication_delay_days": 8,
            "procurement_method_open_flag": True,
            "conflict_of_interest_declaration": "present and flagged clear",
        },
    },
]


def render_record(rec: dict) -> str:
    lines = ["Procurement decision under review:", ""]
    for k, v in rec["fields"].items():
        lines.append(f"- {k.replace('_', ' ')}: {v}")
    return "\n".join(lines)


def try_parse_verdict(raw: str) -> tuple[bool, str | None, bool]:
    """Return (parsed_ok, verdict, needed_fence_strip)."""
    needed_strip = False
    text = raw.strip()
    if text.startswith("```"):
        # Markdown fence — a portability wrinkle. Strip and retry.
        needed_strip = True
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        obj = json.loads(text)
        return True, obj.get("verdict"), needed_strip
    except (json.JSONDecodeError, AttributeError):
        return False, None, needed_strip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sonnet",
        action="store_true",
        help="Option (B): use claude-sonnet-4-6 with temperature=0 (temp-matchable).",
    )
    args = ap.parse_args()

    if not E2_SYSTEM_PROMPT.exists():
        return _fail(f"E2 system prompt not found at {E2_SYSTEM_PROMPT}")
    system_prompt = E2_SYSTEM_PROMPT.read_text()

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    if args.sonnet:
        model = "claude-sonnet-4-6"
        extra = {"temperature": 0}  # Sonnet 4.6 still accepts temperature
        temp_note = "temperature=0 (Sonnet 4.6 accepts it)"
    else:
        model = "claude-opus-4-7"
        extra = {}  # Opus 4.7 REMOVED temperature — sending it 400s
        temp_note = "no temperature param (Opus 4.7 removed it; would 400)"

    print(f"==> E3 Claude feasibility spike — mechanics only")
    print(f"    Model:        {model}")
    print(f"    Sampling:     {temp_note}")
    print(f"    Records:      {len(THROWAWAY_RECORDS)} throwaway synthetic (NOT the corpus)")
    print(f"    System prompt: {E2_SYSTEM_PROMPT} (verbatim)")
    print()

    confirmed_model = None
    any_fence_strip = False
    all_parsed = True

    for rec in THROWAWAY_RECORDS:
        user_msg = render_record(rec)
        t0 = time.monotonic()
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
                **extra,
            )
        except anthropic.NotFoundError as e:
            return _fail(f"Model {model} not found / not accessible on this key: {e}")
        except anthropic.AuthenticationError:
            return _fail("ANTHROPIC_API_KEY invalid or missing.")
        except anthropic.PermissionDeniedError as e:
            return _fail(f"Key lacks access to {model}: {e}")
        except anthropic.BadRequestError as e:
            return _fail(f"400 from {model} — likely the temperature/param issue: {e}")
        except anthropic.APIError as e:
            return _fail(f"API error from {model}: {e}")
        dt = (time.monotonic() - t0) * 1000

        confirmed_model = resp.model
        raw = "".join(b.text for b in resp.content if b.type == "text")
        parsed_ok, verdict, needed_strip = try_parse_verdict(raw)
        any_fence_strip = any_fence_strip or needed_strip
        all_parsed = all_parsed and parsed_ok

        print(f"--- {rec['label']} ---")
        print(f"    parsed_ok={parsed_ok}  verdict={verdict!r}  "
              f"fence_strip_needed={needed_strip}  latency={dt:.0f}ms")
        print(f"    tokens: in={resp.usage.input_tokens} out={resp.usage.output_tokens}")
        print(f"    raw: {raw[:240]}")
        print()

    # Summary — the four mechanical questions.
    print("==> SPIKE SUMMARY")
    print(f"    1. Model reached by key:   {confirmed_model}")
    print(f"    2. Verbatim-scaffold parse: {'CLEAN' if all_parsed and not any_fence_strip else ('NEEDS SHIM' if all_parsed else 'FAILED')}")
    if any_fence_strip:
        print(f"       (some responses were markdown-fenced — option (b) parsing shim recommended,")
        print(f"        keeps the prompt byte-identical, adapts only verdict extraction)")
    print(f"    3. Sampling:               {temp_note}")
    print(f"    4. Latency/tokens:         see per-record above")
    print()
    print("    DECISION FOR SAM (pin before lock):")
    print("      (A) claude-opus-4-7, no temperature  — most capable; determinism via effort, not temp")
    print("      (B) claude-sonnet-4-6, temperature=0 — matches gpt-5.4 temp-0 more closely; less capable")
    print("      Re-run with --sonnet to compare option (B).")
    return 0


def _fail(msg: str) -> int:
    print(f"SPIKE FAILED: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
