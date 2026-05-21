"""Per-rule operator inversion for the Permuted-Policy diagnostic.

## What this is

The control flips each rule's primary `condition` operator into its
opposite so the resulting policy enforces the **negation** of the
ratified policy. A record that legitimately violates PROC-001-S53
("publication_delay_days > 30") under the unperturbed policy
**no longer violates** the inverted rule (which fires when
publication_delay_days is *below* 30). The flip-direction is uniform
across all six rules — no rule is left unperturbed (see
`planning/experiment_design.md` §"Diagnostic Controls": "the inversion
is applied uniformly across all 6 rules (no rule preserved) so the
agent cannot ride along on partial-policy correctness.").

## Inversion mapping (per condition key)

We invert the **operator key**, leaving the threshold value / list
verbatim. Inversions are involutive — applying twice returns the
original condition.

| Original key       | Inverted key         | Rule(s) using it        |
|--------------------|----------------------|-------------------------|
| `max`              | `min`                | PROC-001, PROC-002, PROC-006 |
| `min`              | `max`                | (round-trip target)     |
| `forbidden`        | `required`           | PROC-003                |
| `required`         | `forbidden`          | (round-trip target)     |
| `required_fields`  | `forbidden_fields`   | PROC-004, PROC-005      |
| `forbidden_fields` | `required_fields`    | (round-trip target)     |

The `field` key (the column the operator runs against) is preserved
verbatim — only the operator name flips. This keeps the *evidence
required* identical between the two passes; only the verdict
condition changes.

## Why not invert the `when` clauses too?

`when` is a scoping predicate — it determines whether a rule's
condition is even evaluated. Inverting `when` would mean the inverted
rule fires on a disjoint set of records from the original, so the
"same record under inverted policy" comparison wouldn't be meaningful.
The build package spec says explicitly: "only inverting `condition`
operators. `when` is presence-checking and inverting it produces
nonsense rather than adversarial logic." We honour that.

## Involutivity

`permute_policy(permute_policy(p))` produces a policy whose **rules**
are byte-identical to `p["rules"]`. The `_permutation_log` field
records the most recent inversion (so a double-application's log
reflects going from inverted-back-to-original); equality at the
rules-and-shape level is what makes the control mathematically sound
and what the test asserts.

## Seed

The seed parameter is reserved for future stochastic variants (e.g.
"flip a random 3-of-6 operators" controls). For E2 it is **locked at
0** — a constant — and unused inside the function body. The seed is
still passed through and **bound into the receipt's integrity hash**
so the same field name carries forward when stochastic variants land
without a receipt-shape change.

## What we DO NOT touch

- `policy_id`, `created_at`, `policy_versions`, `policy_rules_hash`,
  rule `code`, `description`, `severity`, `name`, `source_ref`,
  `when` clause, `is_shadow`, `rule_type`, `policy_id` on each rule.
  Only the `condition` block's operator key is renamed.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping


LOCKED_PERMUTATION_SEED = 0
"""The seed value E2 binds into every Permuted-Policy receipt. Locked
constant at v0.2 — future variants may carry other seeds; this one is
the only seed E2 emits."""

PERMUTATION_LOG_KEY = "_permutation_log"
"""Key under which the per-rule inversion record is persisted on the
returned policy dict. The leading underscore marks it as runner-local
metadata (not part of any ratified-policy schema)."""

# Operator-key inversion pairs. Order matters only for readability.
# Each pair is a bijection — inverting twice returns the original key.
_OPERATOR_INVERSIONS: tuple[tuple[str, str], ...] = (
    ("max", "min"),
    ("forbidden", "required"),
    ("required_fields", "forbidden_fields"),
)

_OPERATOR_INVERSION_MAP: dict[str, str] = {}
for _a, _b in _OPERATOR_INVERSIONS:
    _OPERATOR_INVERSION_MAP[_a] = _b
    _OPERATOR_INVERSION_MAP[_b] = _a

# Non-operator keys we leave verbatim inside a `condition` block. Any
# key not in this set AND not in _OPERATOR_INVERSION_MAP is unknown
# and triggers a hard stop — the spec demands we not half-implement.
_CONDITION_PASS_THROUGH_KEYS: frozenset[str] = frozenset({"field"})


class PolicyPermutationError(RuntimeError):
    """Raised when a rule's condition can't be mechanically inverted
    (e.g. the operator key isn't in the locked inversion map, or no
    operator key is present at all). Surfacing rather than guessing —
    see the build package's stop conditions."""


def _invert_condition(condition: Mapping[str, Any], rule_code: str) -> dict[str, Any]:
    """Return a new dict with the operator key inverted.

    Exactly one operator key must be present in `condition`. If zero
    or more than one are present we cannot pick a "primary" operator
    without ambiguity, so we raise. The build package spec says: "If
    a rule's condition is structurally too complex to mechanically
    invert, STOP and surface."
    """
    if not isinstance(condition, Mapping):
        raise PolicyPermutationError(
            f"Rule {rule_code!r}: condition is not a mapping (got {type(condition).__name__}); "
            f"cannot mechanically invert."
        )

    operator_keys_present = [k for k in condition.keys() if k in _OPERATOR_INVERSION_MAP]
    if len(operator_keys_present) == 0:
        raise PolicyPermutationError(
            f"Rule {rule_code!r}: no invertible operator key found in condition "
            f"(keys present: {sorted(condition.keys())}). The locked inversion "
            f"mapping covers: {sorted(_OPERATOR_INVERSION_MAP)}. Surface to Sam."
        )
    if len(operator_keys_present) > 1:
        raise PolicyPermutationError(
            f"Rule {rule_code!r}: more than one operator key present "
            f"({operator_keys_present}); cannot pick a primary operator to invert. "
            f"Surface to Sam."
        )

    operator_key = operator_keys_present[0]
    inverted_key = _OPERATOR_INVERSION_MAP[operator_key]

    # Reject unknown non-operator keys — preserving them silently could
    # hide a future schema extension whose semantics would interact with
    # the inversion.
    for key in condition:
        if key in _CONDITION_PASS_THROUGH_KEYS:
            continue
        if key in _OPERATOR_INVERSION_MAP:
            continue
        raise PolicyPermutationError(
            f"Rule {rule_code!r}: unknown condition key {key!r}; "
            f"the locked inverter knows only operator keys "
            f"{sorted(_OPERATOR_INVERSION_MAP)} plus pass-through "
            f"{sorted(_CONDITION_PASS_THROUGH_KEYS)}. Surface to Sam."
        )

    inverted: dict[str, Any] = {}
    for key, value in condition.items():
        if key == operator_key:
            inverted[inverted_key] = copy.deepcopy(value)
        else:
            inverted[key] = copy.deepcopy(value)
    return inverted


def permute_policy(policy: Mapping[str, Any], seed: int = LOCKED_PERMUTATION_SEED) -> dict[str, Any]:
    """Return a deep-copied policy with every rule's primary operator
    inverted and a `_permutation_log` recording each per-rule
    transformation.

    Determinism: same input policy + same seed → byte-identical output
    (modulo dict insertion order, which we treat as semantically
    equivalent since downstream rendering uses sort_keys=True).

    Involutivity: `permute_policy(permute_policy(p))["rules"]` equals
    `p["rules"]` (verified in tests). The `_permutation_log` field is
    rewritten on each application — a double-application's log
    therefore records the going-back inversion, not absence.

    Seed: ignored in E2 (locked constant LOCKED_PERMUTATION_SEED). The
    parameter is preserved so future stochastic variants can ride the
    same call signature; the seed is also injected into the receipt
    integrity payload so downstream verifiers can pin the variant.

    Raises PolicyPermutationError when a rule's condition cannot be
    mechanically inverted (unknown operator key, ambiguous primary
    operator, etc.). The build-package contract requires we surface
    rather than half-implement.
    """
    if "rules" not in policy or not isinstance(policy["rules"], list):
        raise PolicyPermutationError(
            "Policy is missing a `rules` list; cannot permute."
        )

    permuted: dict[str, Any] = copy.deepcopy(dict(policy))
    # Always strip any prior _permutation_log so this function's output
    # never accumulates stale provenance; we rewrite it below.
    permuted.pop(PERMUTATION_LOG_KEY, None)

    log_entries: list[dict[str, Any]] = []
    new_rules: list[dict[str, Any]] = []

    for rule in permuted["rules"]:
        if not isinstance(rule, Mapping):
            raise PolicyPermutationError(
                f"Encountered non-mapping rule entry: {rule!r}; cannot permute."
            )
        rule_code = rule.get("code") or "<unknown>"
        original_condition = rule.get("condition")
        if original_condition is None:
            raise PolicyPermutationError(
                f"Rule {rule_code!r}: no `condition` block; cannot permute."
            )

        inverted_condition = _invert_condition(original_condition, rule_code)
        new_rule = dict(rule)
        new_rule["condition"] = inverted_condition
        new_rules.append(new_rule)

        log_entries.append(
            {
                "rule_code": rule_code,
                "original_condition": copy.deepcopy(dict(original_condition)),
                "inverted_condition": copy.deepcopy(inverted_condition),
            }
        )

    permuted["rules"] = new_rules
    permuted[PERMUTATION_LOG_KEY] = {
        "seed": int(seed),
        "entries": log_entries,
    }
    return permuted
