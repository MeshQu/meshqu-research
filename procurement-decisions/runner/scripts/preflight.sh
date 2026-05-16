#!/usr/bin/env bash
# Preflight checks for any procurement-decisions runner phase.
#
# Runs before dry-run, full-run, reproducibility-rerun, AND OBS-401 smoke.
# Validates the observability stack + meshqu-api endpoints + filesystem
# preconditions the runner depends on. Fail-fast: any check non-PASS aborts.
#
# Usage:
#   bash scripts/preflight.sh                       # default local stack
#   MESHQU_RUNNER_GRAFANA_URL=https://grafana.staging.meshqu.com \
#   MESHQU_RUNNER_GRAFANA_USER=... MESHQU_RUNNER_GRAFANA_PASSWORD=... \
#   MESHQU_API_URL=https://api.staging.meshqu.com \
#     bash scripts/preflight.sh                     # staging
#
# Exit codes:
#   0  all checks PASS
#   1  one or more checks FAIL — full output shows which

set -uo pipefail

GRAFANA_URL="${MESHQU_RUNNER_GRAFANA_URL:-http://localhost:3101}"
GRAFANA_USER="${MESHQU_RUNNER_GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${MESHQU_RUNNER_GRAFANA_PASSWORD:-admin}"
DASHBOARD_UID="${MESHQU_RUNNER_DASHBOARD_UID:-experiment-tenant-observability}"
RENDERER_URL="${RENDERER_URL:-http://localhost:8081}"
MESHQU_API_URL="${MESHQU_API_URL:-http://localhost:3002}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9091}"
RESULTS_DIR="${MESHQU_RUNNER_RESULTS_DIR:-$(cd "$(dirname "$0")/../.." && pwd)/results}"

failures=0
check() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  if [ "$status" = "PASS" ]; then
    printf "  \033[32m✓ PASS\033[0m  %-40s %s\n" "$name" "$detail"
  else
    printf "  \033[31m✗ FAIL\033[0m  %-40s %s\n" "$name" "$detail"
    failures=$((failures + 1))
  fi
}

echo
echo "=== preflight  $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "  GRAFANA_URL    = $GRAFANA_URL"
echo "  MESHQU_API_URL = $MESHQU_API_URL"
echo "  DASHBOARD_UID  = $DASHBOARD_UID"
echo "  RESULTS_DIR    = $RESULTS_DIR"
echo

# 1. Grafana reachable + dashboard present
http=$(curl -sS -o /tmp/preflight-grafana.json -w "%{http_code}" \
  -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
  "$GRAFANA_URL/api/dashboards/uid/$DASHBOARD_UID" || echo "000")
if [ "$http" = "200" ]; then
  title=$(python3 -c 'import json; print(json.load(open("/tmp/preflight-grafana.json"))["dashboard"]["title"])' 2>/dev/null || echo "?")
  version=$(python3 -c 'import json; print(json.load(open("/tmp/preflight-grafana.json"))["dashboard"]["version"])' 2>/dev/null || echo "?")
  check "grafana reachable" "PASS" "title=\"$title\" version=$version"
else
  check "grafana reachable" "FAIL" "HTTP $http — $GRAFANA_URL/api/dashboards/uid/$DASHBOARD_UID"
fi

# 2. Renderer reachable (only relevant for the same stack as Grafana — Grafana
#    is what calls the renderer over its internal network, so we just probe
#    Grafana's render endpoint as a smoke test).
http=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 \
  -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
  "$GRAFANA_URL/render/d/$DASHBOARD_UID?orgId=1&width=400&height=300" || echo "000")
if [ "$http" = "200" ]; then
  check "grafana → renderer pipe" "PASS" "$GRAFANA_URL/render/... HTTP 200"
else
  check "grafana → renderer pipe" "FAIL" "HTTP $http — renderer likely down or unreachable"
fi

# 3. meshqu-api healthy
http=$(curl -sS -o /tmp/preflight-api.json -w "%{http_code}" \
  "$MESHQU_API_URL/v1/health" || echo "000")
if [ "$http" = "200" ]; then
  status=$(python3 -c 'import json; print(json.load(open("/tmp/preflight-api.json")).get("status","?"))' 2>/dev/null || echo "?")
  version=$(python3 -c 'import json; print(json.load(open("/tmp/preflight-api.json")).get("version","?"))' 2>/dev/null || echo "?")
  check "meshqu-api healthy" "PASS" "status=$status version=$version"
else
  check "meshqu-api healthy" "FAIL" "HTTP $http — $MESHQU_API_URL/v1/health"
fi

# 4. meshqu-api /metrics endpoint reachable (used by Prometheus scrape).
http=$(curl -sS -o /dev/null -w "%{http_code}" "$MESHQU_API_URL/metrics" || echo "000")
if [ "$http" = "200" ]; then
  check "meshqu-api /metrics" "PASS" "(Prometheus scrape target)"
else
  check "meshqu-api /metrics" "FAIL" "HTTP $http"
fi

# 5. Prometheus reachable + scraping meshqu-api.
if curl -sS --max-time 5 "$PROMETHEUS_URL/-/healthy" >/dev/null 2>&1; then
  scrape_health=$(curl -sS "$PROMETHEUS_URL/api/v1/targets?state=any" 2>/dev/null \
    | python3 -c '
import json, sys
d = json.load(sys.stdin)
api = [t for t in d["data"]["activeTargets"] if t["labels"].get("job") == "meshqu-api"]
print(api[0]["health"] if api else "missing")' 2>/dev/null || echo "?")
  if [ "$scrape_health" = "up" ]; then
    check "prometheus → meshqu-api scrape" "PASS" "target health=up"
  else
    check "prometheus → meshqu-api scrape" "FAIL" "target health=$scrape_health"
  fi
else
  check "prometheus reachable" "FAIL" "$PROMETHEUS_URL/-/healthy unreachable"
fi

# 6. Filesystem preconditions — runner needs to write screenshots, audit, dashboards.
for sub in observability/screenshots observability/dashboards audit; do
  dir="$RESULTS_DIR/$sub"
  if [ -d "$dir" ] && [ -w "$dir" ]; then
    check "results/$sub writable" "PASS" "$dir"
  elif [ -d "$dir" ]; then
    check "results/$sub writable" "FAIL" "exists but not writable: $dir"
  else
    # Auto-create — append-only convention, doesn't hurt.
    if mkdir -p "$dir" 2>/dev/null; then
      check "results/$sub writable" "PASS" "created: $dir"
    else
      check "results/$sub writable" "FAIL" "cannot create: $dir"
    fi
  fi
done

# 7. Canonical dashboard JSON readable from the monorepo (OBS-206 mirror source).
MONOREPO_DASH="${MESHQU_RUNNER_MONOREPO_DASHBOARD_PATH:-/Users/sam/Projects/tradequ/monitoring/dashboards/experiment-tenant-observability.json}"
if [ -r "$MONOREPO_DASH" ]; then
  sha=$(shasum -a 256 "$MONOREPO_DASH" | awk '{print substr($1,1,12)}')
  check "monorepo dashboard JSON" "PASS" "sha256(prefix)=$sha"
else
  check "monorepo dashboard JSON" "FAIL" "not readable: $MONOREPO_DASH"
fi

echo
if [ "$failures" -eq 0 ]; then
  echo -e "\033[32mpreflight: PASS — all $((6+1)) checks green\033[0m"
  exit 0
else
  echo -e "\033[31mpreflight: FAIL — $failures check(s) need fixing before any run\033[0m"
  exit 1
fi
