# tests/common.sh — shared helpers sourced by every test file via run_tests.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

pass()    { echo -e "${GREEN}  ✓ PASS${RESET} $1"; PASS=$((PASS + 1)); }
fail()    { echo -e "${RED}  ✗ FAIL${RESET} $1"; FAIL=$((FAIL + 1)); }
skip()    { echo -e "${YELLOW}  - SKIP${RESET} $1"; SKIP=$((SKIP + 1)); }
section() { echo -e "\n${CYAN}${BOLD}══ $1 ══${RESET}"; }

H_SLUG="X-School-Slug: ${SCHOOL_SLUG}"
H_JSON="Content-Type: application/json"

req() {
  local method="$1" path="$2" body="${3:-}" token="${4:-}"
  local auth_header=()
  [[ -n "$token" ]] && auth_header=(-H "Authorization: Bearer $token")
  local data_args=()
  [[ -n "$body" ]] && data_args=(-d "$body")

  curl -s -o /tmp/_body -w "%{http_code}" \
    -X "$method" \
    -H "$H_JSON" \
    -H "$H_SLUG" \
    "${auth_header[@]}" \
    "${data_args[@]}" \
    "${BASE_URL}${path}"
  echo ""
  cat /tmp/_body
}

# Pure-bash string splits — no pipes, so never trigger SIGPIPE on large bodies.
status_of() { echo "${1%%$'\n'*}"; }
body_of()   { echo "${1#*$'\n'}"; }
jq_get()    { echo "$1" | jq -r "$2" 2>/dev/null || echo ""; }

check() {
  local label="$1" resp="$2" expected="${3:-200}"
  local st; st=$(status_of "$resp")
  if [[ "$st" == "$expected" ]]; then
    pass "$label (HTTP $st)"
  else
    fail "$label — expected $expected, got $st | $(body_of "$resp" | jq -c . 2>/dev/null || body_of "$resp" | head -c 200)"
  fi
}

# Delete all resources matching a jq filter on a list endpoint.
# Runs serially (no process substitution) to avoid /tmp/_body races.
# Usage: _cleanup "/api/sessions/" 'select(.name == "2024/2025") | .id'
_cleanup() {
  local endpoint="$1" filter="$2"
  local r body ids id
  r=$(req GET "$endpoint" "" "$ADMIN_TOKEN")
  body=$(body_of "$r")
  ids=$(printf '%s' "$body" | jq -r "(.results // .) | .[] | ${filter} | tostring" 2>/dev/null || echo "")
  [[ -z "$ids" ]] && return 0
  while IFS= read -r id; do
    [[ -n "$id" && "$id" != "null" ]] && \
      req DELETE "${endpoint}${id}/" "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
  done <<< "$ids"
}
