# Note on the status line in predictions.md

[`predictions.md`](predictions.md) opens with a status line that says "pre-lock" and "Not yet locked". Those sentences are stale prose. They were written before the tag landed and they describe a state that no longer holds.

The lock is the git tag `v0.3-predictions-locked` (2026-05-28, commit `ba4ebfb`). The tag binds the predictions, the locked content packages (Arm C payload, L4-without-nudge variant, rubric protocol, subset selection rule, Claude version pin), and the policy snapshot at their pre-run state. All evaluation calls came after the tag. The published writeup (MRP-2026-04) cites the tag as the pre-registration anchor.

The file itself is preserved unmodified, including its stale opening sentences. The tagged content is the historical record, and the pre-registration guarantee depends on the file matching what the tag covers. Editing the file after the fact, even to fix a status line, would break that property. This note is the correction; the file stays as it was.

To verify the lock yourself:

```
git show v0.3-predictions-locked:procurement-context-disambiguation/planning/predictions.md
```

The output matches the file on main byte for byte.

Earlier lock tags follow the same per-experiment convention: E1 at `v0.1-predictions-locked`, E2 at `v0.2-predictions-locked`. E2's file also matches its tag byte for byte. E1's file received one transparent post-tag edit (PR #5) that filled in the lock-commit SHA in its status box; the predictions themselves are unchanged from the tag.
