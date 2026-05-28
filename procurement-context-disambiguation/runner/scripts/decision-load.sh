#!/usr/bin/env bash
# Decision-source: manual load generator for OBS-401 smoke testing.
#
# **Intentionally vestigial scaffolding.** Drives N decisions through
# meshqu-api with a tenant + decision_type AND writes a row to
# results/audit/decision_traces.jsonl per successful decision tagged
# `source: "decision-load-smoke"`.
#
# This script's audit-writing duty is RETIRED the moment the Inspect-AI
# eval loop integrates with RunController.after_record() — at that point
# rows get written with `source: "inspect-eval"` from inside the runner,
# and this script either gets deleted or becomes a generic "fire N API
# requests" tool with no audit-writing duty. The `source` discriminator
# in results/audit/README.md and the validator's source-conditional null
# checks let the two writers coexist during the transition.
#
# See results/audit/README.md "decision_traces.jsonl schema" for the
# full schema + nullability table by source.
#
# Shaped as one of N possible decision sources — the future OCDS substrate
# adapter (per planning/experiment_design.md) will be another. The runner's
# lifecycle hooks fire in parallel; this script doesn't touch the runner's
# controller directly.
#
# Usage:
#   # Local smoke (10 decisions against a throwaway tenant):
#   bash scripts/decision-load.sh
#
#   # Override count + decision type:
#   bash scripts/decision-load.sh --count 25 --decision-type lc_approval
#
#   # Coordinate run_id with a runner smoke (recommended for OBS-401):
#   RUN_ID=$(python -m meshqu_runner.cli smoke 2>&1 | awk '/run_id=/{print $NF}')
#   bash scripts/decision-load.sh --run-id "$RUN_ID"
#
#   # Against staging:
#   MESHQU_API_URL=https://api.staging.meshqu.com \
#   MESHQU_API_KEY=... \
#     bash scripts/decision-load.sh --tenant 00000000-0000-4000-8000-... --count 10
#
# Output:
#   - stdout: one decision JSON per line (JSONL) — short summary, for piping
#   - stderr: tally + warnings
#   - results/audit/decision_traces.jsonl: one append per successful decision
#     (full schema with smoke-source nulls per the README's nullability table)
#
# Exit 0 if all decisions succeeded; non-zero with the count of failures otherwise.
#
# Tenant convention for local smoke testing: the local Supabase seed
# migration provisions `00000000-0000-0000-0000-000000000002` (Test
# Organization) as a clean throwaway tenant — no policies by default,
# explicitly named for testing. Real experiment runs use the
# experiment-procurement UUID configured in staging.
#
# Before running this script the throwaway tenant needs an active policy
# for the chosen decision_type. To seed one for local smoke:
#
#   curl -X POST http://localhost:3002/v1/policies \
#     -H "X-MeshQu-Tenant-Id: 00000000-0000-0000-0000-000000000002" \
#     -d '{"code":"SMOKE-TXN-001","name":"Smoke",
#          "decision_type":"transaction_approval",
#          "rules":[{"code":"AMOUNT-CAP","name":"cap","rule_type":"threshold",
#                    "severity":"high","condition":{"field":"amount","max":100000}}]}'
#   # SKIP_AUTH=true auto-ratifies on local dev. Verify with:
#   curl http://localhost:3002/v1/policies -H "X-MeshQu-Tenant-Id: 00000...02"

set -uo pipefail

# Defaults — overridable via --flags
TENANT="${TENANT:-00000000-0000-0000-0000-000000000002}"
COUNT=10
DECISION_TYPE="transaction_approval"
SOURCE="manual"
API_URL="${MESHQU_API_URL:-http://localhost:3002}"
API_KEY="${MESHQU_API_KEY:-}"
RUN_ID=""
AUDIT_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --tenant)         TENANT="$2"; shift 2 ;;
    --count)          COUNT="$2"; shift 2 ;;
    --decision-type)  DECISION_TYPE="$2"; shift 2 ;;
    --source)         SOURCE="$2"; shift 2 ;;
    --run-id)         RUN_ID="$2"; shift 2 ;;
    --audit-dir)      AUDIT_DIR="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" >&2
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Resolve run_id: --run-id wins, else env var, else generate a fresh UUID.
if [ -z "$RUN_ID" ]; then
  RUN_ID="${MESHQU_RUNNER_RUN_ID:-$(python3 -c 'import uuid; print(uuid.uuid4())')}"
fi

# Resolve audit dir: --audit-dir wins, else env var, else repo-relative default.
if [ -z "$AUDIT_DIR" ]; then
  AUDIT_DIR="${MESHQU_RUNNER_RESULTS_DIR:-$(cd "$(dirname "$0")/../.." && pwd)/results}/audit"
fi
TRACES_FILE="$AUDIT_DIR/decision_traces.jsonl"
mkdir -p "$AUDIT_DIR"

case "$SOURCE" in
  manual) ;;
  ocds-adapter) echo "ocds-adapter source not yet implemented — see planning/experiment_design.md" >&2; exit 2 ;;
  *) echo "unknown --source: $SOURCE  (allowed: manual, ocds-adapter)" >&2; exit 2 ;;
esac

# Auth: --api-key wins; if absent and API_URL is localhost, allow SKIP_AUTH path.
auth_header=()
if [ -n "$API_KEY" ]; then
  auth_header=(-H "Authorization: Bearer $API_KEY")
elif [[ "$API_URL" != *"localhost"* ]]; then
  echo "WARN: no MESHQU_API_KEY set and API_URL=$API_URL is not localhost — this will likely 401" >&2
fi

echo "decision-load: source=$SOURCE tenant=$TENANT count=$COUNT type=$DECISION_TYPE api=$API_URL" >&2
echo "  run_id=$RUN_ID" >&2
echo "  audit=$TRACES_FILE" >&2

succeeded=0
failed=0
not_found_warnings=0

for i in $(seq 1 "$COUNT"); do
  # Manual source uses a deterministic-ish payload so receipts are reproducible.
  # Synthetic amounts that span the policy thresholds (typical experiment uses
  # transaction-approval with amount-based rules).
  amount=$((1000 + (i * 137) % 95000))
  idem="smoke-$(date -u +%Y%m%dT%H%M%S)-record-$i"

  resp=$(mktemp)
  http=$(curl -sS -o "$resp" -w "%{http_code}" \
    -X POST "$API_URL/v1/decisions/record" \
    -H "X-MeshQu-Tenant-Id: $TENANT" \
    -H "X-MeshQu-Idempotency-Key: $idem" \
    -H "Content-Type: application/json" \
    ${auth_header[@]+"${auth_header[@]}"} \
    -d "{\"context\":{\"decision_type\":\"$DECISION_TYPE\",\"fields\":{\"amount\":$amount,\"actor\":\"smoke-test\"}}}" \
    || echo "000")

  case "$http" in
    200|201)
      # Emit a single-line JSON summary per decision (for downstream pipes) +
      # append a full audit row to decision_traces.jsonl tagged
      # source=decision-load-smoke. Nullable fields (agent_*, ocid, rekor_*)
      # are explicitly null per the schema's source-conditional nullability
      # table (results/audit/README.md). When the Inspect-AI loop lands,
      # those nulls become populated and `source` flips to "inspect-eval".
      RUN_ID_VAR="$RUN_ID" TRACES_FILE_VAR="$TRACES_FILE" \
      python3 -c "
import json, os, sys
from datetime import datetime, timezone

with open('$resp') as f:
    body = json.load(f)
decision = body.get('decision', {})
result = decision.get('result') or body.get('result') or {}

decision_id = decision.get('id') or body.get('id')
violations = result.get('violations') or []
verdict = result.get('decision') or decision.get('decision')

# Stdout summary (for piping; back-compat with the prior shape).
print(json.dumps({
  'record_index': $i - 1,
  'http_status': $http,
  'decision_id': decision_id,
  'outcome': verdict,
  'amount': $amount,
  'idempotency_key': '$idem',
  'is_new': body.get('isNew'),
}))

# Append to decision_traces.jsonl (one row per decision, append-only).
trace = {
    'ts': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
    'run_id': os.environ['RUN_ID_VAR'],
    'source': 'decision-load-smoke',
    'record_index': $i - 1,
    'ocid': None,  # no OCDS substrate yet; populated by future inspect-eval source
    'decision_id': decision_id,
    'policy_snapshot_digest': result.get('policy_snapshot_digest') or result.get('evaluated_rules_hash'),
    'agent_verdict': None,  # no agent in smoke; populated by inspect-eval
    'agent_reasoning_sha256': None,
    'meshqu_verdict': verdict,
    'rules_fired': [v.get('rule_code') for v in violations if isinstance(v, dict)],
    'agree': None,  # no agent comparison in smoke
    'latency_ms': {
        'agent': None,
        'meshqu_evaluate': result.get('evaluation_time_ms'),
        'rekor_anchor': None,  # async; not visible at write time
        'total': body.get('duration_ms'),
    },
    'receipt_integrity_hash': result.get('integrity_hash'),
    'receipt_signature_kid': result.get('signature_kid'),
    'rekor_log_index': None,  # async patch-back
    'rekor_log_entry_uuid': None,  # async patch-back
}
with open(os.environ['TRACES_FILE_VAR'], 'a') as f:
    f.write(json.dumps(trace) + '\n')
" || true
      succeeded=$((succeeded + 1))
      ;;
    404)
      err_code=$(python3 -c 'import json,sys; print(json.load(open("'"$resp"'")).get("error",{}).get("code","?"))' 2>/dev/null || echo "?")
      if [ "$err_code" = "NO_ACTIVE_POLICIES" ]; then
        if [ "$not_found_warnings" -eq 0 ]; then
          cat >&2 <<EOF

ERROR: no active policy for tenant=$TENANT decision_type=$DECISION_TYPE on $API_URL.

Create one before running this script. Options:
  A. Via the API: POST $API_URL/v1/policies with a minimal threshold rule.
  B. Via the demo seed script: see apps/meshqu-demo seeds (if available).
  C. Use an existing tenant + decision_type pair that already has a policy.

This script doesn't auto-create policies because policy creation is an
authorized side-effect that should be deliberate. The future OCDS substrate
adapter will use a pre-provisioned experiment tenant with a known policy.

EOF
          not_found_warnings=1
        fi
      else
        echo "record $i: HTTP 404 code=$err_code" >&2
      fi
      failed=$((failed + 1))
      ;;
    *)
      echo "record $i: HTTP $http" >&2
      cat "$resp" >&2
      echo "" >&2
      failed=$((failed + 1))
      ;;
  esac
  rm -f "$resp"
done

echo "" >&2
echo "decision-load: $succeeded/$COUNT succeeded, $failed failed" >&2

if [ "$failed" -gt 0 ]; then
  exit 1
fi
exit 0
