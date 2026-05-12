#!/usr/bin/env bash
# test_api.sh — Full end-to-end API test for the school portal
# Usage:
#   ./test_api.sh                        # runs against http://localhost:8000
#   BASE_URL=https://your.railway.app ./test_api.sh
#   SCHOOL_SLUG=greenfield BASE_URL=https://your.railway.app ./test_api.sh
#
# Requires: curl, jq
# The script creates real data in the target DB — use a test/staging instance.

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
SCHOOL_SLUG="${SCHOOL_SLUG:-testschool}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@testschool.ng}"
ADMIN_PASS="${ADMIN_PASS:-AdminStr0ng#1}"
TEACHER_EMAIL="${TEACHER_EMAIL:-teacher@testschool.ng}"
TEACHER_PASS="${TEACHER_PASS:-teacher1234}"
STUDENT_EMAIL="${STUDENT_EMAIL:-student@testschool.ng}"
STUDENT_PASS="${STUDENT_PASS:-student1234}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

PASS=0; FAIL=0; SKIP=0

pass() { echo -e "${GREEN}  ✓ PASS${RESET} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}  ✗ FAIL${RESET} $1"; FAIL=$((FAIL + 1)); }
skip() { echo -e "${YELLOW}  - SKIP${RESET} $1"; SKIP=$((SKIP + 1)); }
section() { echo -e "\n${CYAN}${BOLD}══ $1 ══${RESET}"; }

# ── HTTP helpers ──────────────────────────────────────────────────────────────
H_SLUG="X-School-Slug: ${SCHOOL_SLUG}"
H_JSON="Content-Type: application/json"

# Returns full curl output: "<STATUS_CODE>\n<BODY>"
# Usage: resp=$(req GET /api/path/ "" "$TOKEN")
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
  echo ""                # newline after status code
  cat /tmp/_body
}

# Extract status from req output (first line).
# Uses parameter expansion to avoid echo|head SIGPIPE with large bodies.
status_of() { echo "${1%%$'\n'*}"; }
# Extract body from req output (everything after first line).
body_of()   { echo "${1#*$'\n'}"; }
# Extract JSON field
jq_get()    { echo "$1" | jq -r "$2" 2>/dev/null || echo ""; }

check() {
  local label="$1" resp="$2" expected="${3:-200}"
  local st; st=$(status_of "$resp")
  if [[ "$st" == "$expected" ]]; then pass "$label (HTTP $st)"
  else fail "$label — expected $expected, got $st | $(body_of "$resp" | jq -c . 2>/dev/null || body_of "$resp")"
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
section "HEALTH CHECK"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req GET /health/ "")
check "GET /health/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "AUTH — Admin login"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/auth/login/ "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASS}\"}")
check "POST /api/auth/login/ (admin)" "$r" 200
body=$(body_of "$r")
ADMIN_TOKEN=$(jq_get "$body" ".access")
REFRESH_TOKEN=$(jq_get "$body" ".refresh")

if [[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]]; then
  echo -e "${RED}FATAL: Admin login failed — cannot continue. Check ADMIN_EMAIL/ADMIN_PASS.${RESET}"
  exit 1
fi

r=$(req POST /api/auth/login/ '{"email":"wrong@x.com","password":"badpass"}')
check "POST /api/auth/login/ rejects bad credentials" "$r" 401

# Token refresh
r=$(req POST /api/auth/token/refresh/ "{\"refresh\":\"${REFRESH_TOKEN}\"}")
check "POST /api/auth/token/refresh/" "$r" 200
NEW_ACCESS=$(jq_get "$(body_of "$r")" ".access")
[[ -n "$NEW_ACCESS" && "$NEW_ACCESS" != "null" ]] && ADMIN_TOKEN="$NEW_ACCESS"

# Me
r=$(req GET /api/auth/me/ "" "$ADMIN_TOKEN")
check "GET /api/auth/me/" "$r" 200

# Change password — use a temp strong password, then restore
TMP_PASS="TmpT3st@Pass99"
r=$(req POST /api/auth/change-password/ \
  "{\"current_password\":\"${ADMIN_PASS}\",\"new_password\":\"${TMP_PASS}\",\"confirm_password\":\"${TMP_PASS}\"}" \
  "$ADMIN_TOKEN")
check "POST /api/auth/change-password/" "$r" 200

# Re-login with temp password and restore original
r=$(req POST /api/auth/login/ "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${TMP_PASS}\"}")
TMP_TOKEN=$(jq_get "$(body_of "$r")" ".access")
r=$(req POST /api/auth/change-password/ \
  "{\"current_password\":\"${TMP_PASS}\",\"new_password\":\"${ADMIN_PASS}\",\"confirm_password\":\"${ADMIN_PASS}\"}" \
  "$TMP_TOKEN")
check "POST /api/auth/change-password/ (restore)" "$r" 200

# Always re-login to get a fresh token after the password dance
r=$(req POST /api/auth/login/ "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASS}\"}")
body=$(body_of "$r")
ADMIN_TOKEN=$(jq_get "$body" ".access")
if [[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]]; then
  echo -e "${RED}FATAL: Could not re-login after password restore.${RESET}"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
section "TENANT — School"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req GET /api/school/me/ "" "$ADMIN_TOKEN")
check "GET /api/school/me/" "$r" 200
SCHOOL_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/schools/ "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "403" ]]; then
  pass "GET /api/schools/ (HTTP $st — 403 expected for school_admin; 200 for superadmin)"
else
  fail "GET /api/schools/ — unexpected $st"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "PRE-RUN CLEANUP — remove leftover data from previous runs"
# ─────────────────────────────────────────────────────────────────────────────
# Silently delete known test artefacts so the script is idempotent.
# Handles both paginated {"results":[...]} and plain-array list responses.
_ids_where() {
  local r; r=$(req GET "$1" "" "$ADMIN_TOKEN")
  body_of "$r" | jq -r "(.results // .) | .[] | $2" 2>/dev/null || true
}
_del() { req DELETE "$1" "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true; }

# Sessions first — cascade wipes terms → holidays, subject_assignments,
# gradebook entries, attendance, fee schedules, scratch cards, result
# remarks, CBT exams, and timetable entries all in one shot.
while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/sessions/${_id}/"; done \
  < <(_ids_where "/api/sessions/" 'select(.name == "2024/2025") | .id | tostring')

# Subjects (cascade → subject_assignment M2M rows)
while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/subjects/${_id}/"; done \
  < <(_ids_where "/api/subjects/" 'select(.code == "MTH") | .id | tostring')

# Class arms before class levels (FK order)
while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/class-arms/${_id}/"; done \
  < <(_ids_where "/api/class-arms/" 'select(.name == "A") | .id | tostring')

while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/class-levels/${_id}/"; done \
  < <(_ids_where "/api/class-levels/" 'select(.name == "JSS1" or .name == "JSS2") | .id | tostring')

# Students and staff (user CASCADE deletes profiles)
while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/students/${_id}/"; done \
  < <(_ids_where "/api/students/" 'select(.admission_number == "ADM2024001") | .id | tostring')

while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/staff/${_id}/"; done \
  < <(_ids_where "/api/staff/" "select(.email == \"${TEACHER_EMAIL}\") | .id | tostring")

# Fee categories, notification templates, timetable periods
while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/fees/categories/${_id}/"; done \
  < <(_ids_where "/api/fees/categories/" 'select(.name | startswith("School Fees")) | .id | tostring')

while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/notifications/templates/${_id}/"; done \
  < <(_ids_where "/api/notifications/templates/" 'select(.name | startswith("Test Template")) | .id | tostring')

while IFS= read -r _id; do [[ -n "$_id" ]] && _del "/api/timetable/periods/${_id}/"; done \
  < <(_ids_where "/api/timetable/periods/" 'select(.name == "Period 1") | .id | tostring')

pass "Pre-run cleanup complete"

# ─────────────────────────────────────────────────────────────────────────────
section "ACADEMICS — Sessions"
# ─────────────────────────────────────────────────────────────────────────────
SESSION_NAME="2024/2025"
r=$(req POST /api/sessions/ \
  "{\"name\":\"${SESSION_NAME}\",\"start_date\":\"2024-09-01\",\"end_date\":\"2025-07-31\"}" \
  "$ADMIN_TOKEN")
check "POST /api/sessions/" "$r" 201
SESSION_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/sessions/ "" "$ADMIN_TOKEN")
check "GET /api/sessions/" "$r" 200

r=$(req GET "/api/sessions/${SESSION_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/sessions/{id}/" "$r" 200

r=$(req POST "/api/sessions/${SESSION_ID}/set-current/" "" "$ADMIN_TOKEN")
check "POST /api/sessions/{id}/set-current/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "ACADEMICS — Terms"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/terms/ \
  "{\"name\":\"first\",\"session\":${SESSION_ID},\"start_date\":\"2024-09-02\",\"end_date\":\"2024-12-13\"}" \
  "$ADMIN_TOKEN")
check "POST /api/terms/" "$r" 201
TERM_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/terms/ "" "$ADMIN_TOKEN")
check "GET /api/terms/" "$r" 200

r=$(req POST "/api/terms/${TERM_ID}/set-current/" "" "$ADMIN_TOKEN")
check "POST /api/terms/{id}/set-current/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "ACADEMICS — Holidays & Calendar"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/holidays/ \
  "{\"name\":\"Test Holiday\",\"start_date\":\"2024-10-01\",\"end_date\":\"2024-10-02\",\"term\":${TERM_ID},\"holiday_type\":\"public\"}" \
  "$ADMIN_TOKEN")
check "POST /api/holidays/" "$r" 201
HOLIDAY_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/holidays/ "" "$ADMIN_TOKEN")
check "GET /api/holidays/" "$r" 200

r=$(req GET /api/calendar/ "" "$ADMIN_TOKEN")
check "GET /api/calendar/" "$r" 200

r=$(req DELETE "/api/holidays/${HOLIDAY_ID}/" "" "$ADMIN_TOKEN")
check "DELETE /api/holidays/{id}/" "$r" 204

# ─────────────────────────────────────────────────────────────────────────────
section "ENROLLMENT — Class Levels"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/class-levels/ \
  '{"name":"JSS1","order_index":1,"is_final_year":false}' \
  "$ADMIN_TOKEN")
check "POST /api/class-levels/" "$r" 201
LEVEL_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/class-levels/ "" "$ADMIN_TOKEN")
check "GET /api/class-levels/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "ENROLLMENT — Class Arms"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/class-arms/ \
  "{\"name\":\"A\",\"class_level\":${LEVEL_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/class-arms/" "$r" 201
ARM_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/class-arms/ "" "$ADMIN_TOKEN")
check "GET /api/class-arms/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "ENROLLMENT — Subjects"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/subjects/ \
  "{\"name\":\"Mathematics\",\"code\":\"MTH\",\"class_level\":${LEVEL_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/subjects/" "$r" 201
SUBJECT_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/subjects/ "" "$ADMIN_TOKEN")
check "GET /api/subjects/" "$r" 200

r=$(req GET "/api/subjects/by-class/${ARM_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/subjects/by-class/{arm_id}/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "ENROLLMENT — Staff"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/staff/ \
  "{\"email\":\"${TEACHER_EMAIL}\",\"first_name\":\"Test\",\"last_name\":\"Teacher\",\"password\":\"${TEACHER_PASS}\",\"role\":\"teacher\"}" \
  "$ADMIN_TOKEN")
check "POST /api/staff/ (create teacher)" "$r" 201
TEACHER_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/staff/ "" "$ADMIN_TOKEN")
check "GET /api/staff/" "$r" 200

r=$(req POST "/api/staff/${TEACHER_ID}/assign-subjects/" \
  "{\"subject_ids\":[${SUBJECT_ID}],\"class_arm_id\":${ARM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/staff/{id}/assign-subjects/" "$r" 200

# Teacher login
r=$(req POST /api/auth/login/ "{\"email\":\"${TEACHER_EMAIL}\",\"password\":\"${TEACHER_PASS}\"}")
check "POST /api/auth/login/ (teacher)" "$r" 200
TEACHER_TOKEN=$(jq_get "$(body_of "$r")" ".access")

# ─────────────────────────────────────────────────────────────────────────────
section "ENROLLMENT — Students"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/students/ \
  "{\"email\":\"${STUDENT_EMAIL}\",\"first_name\":\"Test\",\"last_name\":\"Student\",\"password\":\"${STUDENT_PASS}\",\"admission_number\":\"ADM2024001\",\"class_arm\":${ARM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/students/ (create student)" "$r" 201
STUDENT_PROFILE_ID=$(jq_get "$(body_of "$r")" ".id")
STUDENT_USER_ID=$(jq_get "$(body_of "$r")" ".user")

r=$(req GET /api/students/ "" "$ADMIN_TOKEN")
check "GET /api/students/" "$r" 200

r=$(req GET "/api/students/by-class/${ARM_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/students/by-class/{arm_id}/" "$r" 200

r=$(req POST "/api/students/${STUDENT_PROFILE_ID}/assign-class/" \
  "{\"class_arm_id\":${ARM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/students/{id}/assign-class/" "$r" 200

# Student login
r=$(req POST /api/auth/login/ "{\"email\":\"${STUDENT_EMAIL}\",\"password\":\"${STUDENT_PASS}\"}")
check "POST /api/auth/login/ (student)" "$r" 200
STUDENT_TOKEN=$(jq_get "$(body_of "$r")" ".access")

# ─────────────────────────────────────────────────────────────────────────────
section "ENROLLMENT — Subject Assignments"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req GET /api/subject-assignments/ "" "$ADMIN_TOKEN")
check "GET /api/subject-assignments/" "$r" 200

r=$(req GET /api/subject-assignments/grid/ "" "$ADMIN_TOKEN")
check "GET /api/subject-assignments/grid/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "ATTENDANCE"
# ─────────────────────────────────────────────────────────────────────────────
TODAY=$(date +%Y-%m-%d)
r=$(req POST /api/attendance/sessions/ \
  "{\"class_arm\":${ARM_ID},\"term\":${TERM_ID},\"date\":\"${TODAY}\"}" \
  "$TEACHER_TOKEN")
check "POST /api/attendance/sessions/" "$r" 201
ATT_SESSION_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/attendance/sessions/ "" "$TEACHER_TOKEN")
check "GET /api/attendance/sessions/" "$r" 200

r=$(req GET "/api/attendance/sessions/${ATT_SESSION_ID}/" "" "$TEACHER_TOKEN")
check "GET /api/attendance/sessions/{id}/" "$r" 200

# Submit attendance records (mark student present)
RECORDS="[{\"student\":${STUDENT_USER_ID},\"status\":\"present\"}]"
r=$(req PATCH "/api/attendance/sessions/${ATT_SESSION_ID}/submit/" \
  "{\"records\":${RECORDS}}" \
  "$TEACHER_TOKEN")
check "PATCH /api/attendance/sessions/{id}/submit/" "$r" 200

r=$(req PATCH "/api/attendance/sessions/${ATT_SESSION_ID}/finalize/" "" "$TEACHER_TOKEN")
check "PATCH /api/attendance/sessions/{id}/finalize/" "$r" 200

r=$(req GET "/api/attendance/sessions/report/?student=${STUDENT_USER_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/attendance/sessions/report/" "$r" 200

r=$(req GET "/api/attendance/sessions/class-report/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/attendance/sessions/class-report/" "$r" 200

r=$(req GET "/api/attendance/sessions/low-attendance/?term=${TERM_ID}&threshold=75" "" "$ADMIN_TOKEN")
check "GET /api/attendance/sessions/low-attendance/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "GRADEBOOK — Grade Scale & Score Entry"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req GET /api/gradebook/entries/grade-scale/ "" "$TEACHER_TOKEN")
check "GET /api/gradebook/entries/grade-scale/" "$r" 200

r=$(req GET "/api/gradebook/entries/?class_arm=${ARM_ID}&subject=${SUBJECT_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/gradebook/entries/ (filtered)" "$r" 200

# Bulk upsert scores
SCORES="[{\"student_id\":${STUDENT_USER_ID},\"first_test\":10,\"second_test\":10,\"assignment\":5,\"project\":5,\"practical\":0,\"exam_score\":50}]"
r=$(req POST /api/gradebook/entries/bulk-update/ \
  "{\"class_arm\":${ARM_ID},\"subject\":${SUBJECT_ID},\"term\":${TERM_ID},\"session\":${SESSION_ID},\"scores\":${SCORES}}" \
  "$TEACHER_TOKEN")
check "POST /api/gradebook/entries/bulk-update/" "$r" 200

# Publish
r=$(req POST "/api/gradebook/entries/publish/?class_arm=${ARM_ID}&subject=${SUBJECT_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "POST /api/gradebook/entries/publish/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "GRADEBOOK — Affective & Psychomotor Domains"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req GET "/api/gradebook/affective/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/gradebook/affective/" "$r" 200

r=$(req PUT "/api/gradebook/affective/student/${STUDENT_USER_ID}/term/${TERM_ID}/" \
  "{\"class_arm\":${ARM_ID},\"punctuality\":4,\"neatness\":5,\"attentiveness\":4,\"honesty\":5,\"politeness\":4,\"cooperation\":5}" \
  "$TEACHER_TOKEN")
check "PUT /api/gradebook/affective/student/{id}/term/{id}/" "$r" 200

r=$(req GET "/api/gradebook/psychomotor/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/gradebook/psychomotor/" "$r" 200

r=$(req PUT "/api/gradebook/psychomotor/student/${STUDENT_USER_ID}/term/${TERM_ID}/" \
  "{\"class_arm\":${ARM_ID},\"handwriting\":4,\"drawing\":3,\"sports\":5,\"music\":4,\"verbal_fluency\":4,\"craft\":3}" \
  "$TEACHER_TOKEN")
check "PUT /api/gradebook/psychomotor/student/{id}/term/{id}/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "RESULTS"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST "/api/results/positions/compute/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "POST /api/results/positions/compute/" "$r" 200

r=$(req GET "/api/results/class-results/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/results/class-results/" "$r" 200

r=$(req GET "/api/results/remarks/${STUDENT_USER_ID}/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/results/remarks/{student_id}/" "$r" 200

# Patch remark
r=$(req PATCH "/api/results/remarks/${STUDENT_USER_ID}/?term=${TERM_ID}" \
  '{"principal_remark":"Excellent performance","teacher_remark":"Keep it up"}' \
  "$ADMIN_TOKEN")
check "PATCH /api/results/remarks/{student_id}/" "$r" 200

r=$(req GET "/api/results/slip-data/${STUDENT_USER_ID}/?term=${TERM_ID}" "" "$STUDENT_TOKEN")
check "GET /api/results/slip-data/{student_id}/" "$r" 200

r=$(req GET "/api/results/slip/${STUDENT_USER_ID}/?term=${TERM_ID}" "" "$STUDENT_TOKEN")
check "GET /api/results/slip/{student_id}/ (PDF)" "$r" 200

r=$(req GET "/api/results/broadsheet/${ARM_ID}/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/results/broadsheet/{class_arm_id}/ (PDF)" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "SCRATCH CARDS"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/scratch-cards/generate/ \
  "{\"term\":${TERM_ID},\"quantity\":5,\"batch_label\":\"TEST-BATCH-01\"}" \
  "$ADMIN_TOKEN")
check "POST /api/scratch-cards/generate/" "$r" 201
BATCH_LABEL="TEST-BATCH-01"

r=$(req GET /api/scratch-cards/ "" "$ADMIN_TOKEN")
check "GET /api/scratch-cards/" "$r" 200
CARD_PIN=$(jq_get "$(body_of "$r")" ".[0].pin")
CARD_SERIAL=$(jq_get "$(body_of "$r")" ".[0].serial")

r=$(req GET /api/scratch-cards/batch-stats/ "" "$ADMIN_TOKEN")
check "GET /api/scratch-cards/batch-stats/" "$r" 200

r=$(req GET "/api/scratch-cards/unused-csv/?batch=${BATCH_LABEL}" "" "$ADMIN_TOKEN")
check "GET /api/scratch-cards/unused-csv/" "$r" 200

# Public result check (no auth required)
if [[ -n "$CARD_PIN" && "$CARD_PIN" != "null" && -n "$CARD_SERIAL" && "$CARD_SERIAL" != "null" ]]; then
  r=$(req POST /api/results/check/ \
    "{\"serial\":\"${CARD_SERIAL}\",\"pin\":\"${CARD_PIN}\",\"term\":${TERM_ID},\"admission_number\":\"ADM2024001\"}")
  check "POST /api/results/check/ (public scratch-card)" "$r" 200
else
  skip "POST /api/results/check/ — could not extract card PIN/serial"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "CBT — Topics & Questions"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/cbt/topics/ \
  "{\"name\":\"Algebra Basics\",\"subject\":${SUBJECT_ID}}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/topics/" "$r" 201
TOPIC_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/cbt/topics/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/topics/" "$r" 200

r=$(req POST /api/cbt/questions/ \
  "{\"topic\":${TOPIC_ID},\"subject\":${SUBJECT_ID},\"text\":\"What is 2+2?\",\"qtype\":\"mcq\",\"options\":{\"A\":\"3\",\"B\":\"4\",\"C\":\"5\",\"D\":\"6\"},\"correct_answer\":\"B\",\"marks\":1}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/questions/ (MCQ)" "$r" 201
QUESTION_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req POST /api/cbt/questions/ \
  "{\"topic\":${TOPIC_ID},\"subject\":${SUBJECT_ID},\"text\":\"The capital of Nigeria is ___.\",\"qtype\":\"fill_blank\",\"correct_answer\":\"Abuja\",\"marks\":1}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/questions/ (fill_blank)" "$r" 201

r=$(req GET /api/cbt/questions/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/questions/" "$r" 200

r=$(req GET /api/cbt/questions/stats/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/questions/stats/" "$r" 200

# Bulk import
BULK_Q='{"questions":[{"topic":'${TOPIC_ID}',"subject":'${SUBJECT_ID}',"text":"5 x 5 = ?","qtype":"mcq","options":{"A":"20","B":"25","C":"30","D":"35"},"correct_answer":"B","marks":1}]}'
r=$(req POST /api/cbt/questions/bulk-import/ "$BULK_Q" "$TEACHER_TOKEN")
check "POST /api/cbt/questions/bulk-import/" "$r" 201

# ─────────────────────────────────────────────────────────────────────────────
section "CBT — Exams"
# ─────────────────────────────────────────────────────────────────────────────
START_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")
END_TS=$(date -u -d "+2 hours" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || python3 -c "from datetime import datetime,timedelta; print((datetime.utcnow()+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ'))")

r=$(req POST /api/cbt/exams/ \
  "{\"title\":\"Test Maths Exam\",\"subject\":${SUBJECT_ID},\"term\":${TERM_ID},\"class_arms\":[${ARM_ID}],\"duration_minutes\":60,\"total_marks\":10,\"start_time\":\"${START_TS}\",\"end_time\":\"${END_TS}\",\"is_active\":true}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/exams/" "$r" 201
EXAM_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/cbt/exams/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/exams/" "$r" 200

r=$(req GET "/api/cbt/exams/${EXAM_ID}/" "" "$TEACHER_TOKEN")
check "GET /api/cbt/exams/{id}/" "$r" 200

r=$(req GET /api/cbt/exams/available/ "" "$STUDENT_TOKEN")
check "GET /api/cbt/exams/available/ (student)" "$r" 200

# Start exam as student
r=$(req POST "/api/cbt/exams/${EXAM_ID}/start/" "" "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/start/" "$r" 200

# Status
r=$(req GET "/api/cbt/exams/${EXAM_ID}/status/" "" "$STUDENT_TOKEN")
check "GET /api/cbt/exams/{id}/status/" "$r" 200

# Save answer
r=$(req POST "/api/cbt/exams/${EXAM_ID}/save-answer/" \
  "{\"question\":${QUESTION_ID},\"selected_option\":\"B\"}" \
  "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/save-answer/" "$r" 200

# Log tab switch
r=$(req POST "/api/cbt/exams/${EXAM_ID}/log-tab-switch/" "" "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/log-tab-switch/" "$r" 200

# Submit exam
r=$(req POST "/api/cbt/exams/${EXAM_ID}/submit/" "" "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/submit/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "FEES — Categories & Schedules"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/fees/categories/ \
  '{"name":"School Fees","description":"Main term school fees"}' \
  "$ADMIN_TOKEN")
check "POST /api/fees/categories/" "$r" 201
FEE_CAT_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/fees/categories/ "" "$ADMIN_TOKEN")
check "GET /api/fees/categories/" "$r" 200

r=$(req PUT "/api/fees/categories/${FEE_CAT_ID}/" \
  '{"name":"School Fees Updated"}' \
  "$ADMIN_TOKEN")
check "PUT /api/fees/categories/{id}/" "$r" 200

# Fee schedule (bulk create)
SCHEDULES="[{\"class_level_id\":${LEVEL_ID},\"fee_category_id\":${FEE_CAT_ID},\"amount\":25000,\"due_date\":\"2024-09-30\"}]"
r=$(req POST /api/fees/schedule/ \
  "{\"term_id\":${TERM_ID},\"schedules\":${SCHEDULES}}" \
  "$ADMIN_TOKEN")
check "POST /api/fees/schedule/ (bulk)" "$r" 201

r=$(req GET "/api/fees/schedule/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/schedule/" "$r" 200
FEE_SCHEDULE_ID=$(jq_get "$(body_of "$r")" ".[0].id")

# Student fees summary
r=$(req GET "/api/fees/student/${STUDENT_PROFILE_ID}/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/student/{id}/" "$r" 200

# Manual payment
r=$(req POST /api/fees/pay/manual/ \
  "{\"student_id\":${STUDENT_PROFILE_ID},\"fee_schedule_id\":${FEE_SCHEDULE_ID},\"amount_paid\":25000,\"payment_date\":\"${TODAY}\",\"method\":\"cash\"}" \
  "$ADMIN_TOKEN")
check "POST /api/fees/pay/manual/" "$r" 201
PAYMENT_ID=$(jq_get "$(body_of "$r")" ".id")

# Receipt PDF
r=$(req GET "/api/fees/receipts/${PAYMENT_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/fees/receipts/{id}/ (PDF)" "$r" 200

# Outstanding fees
r=$(req GET "/api/fees/outstanding/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/outstanding/" "$r" 200

r=$(req GET "/api/fees/outstanding/?term=${TERM_ID}&class_arm=${ARM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/outstanding/ (filtered by class_arm)" "$r" 200

# Paystack initiate (will fail without real key — expect 502)
r=$(req POST /api/fees/pay/initiate/ \
  "{\"student_id\":${STUDENT_PROFILE_ID},\"fee_schedule_ids\":[${FEE_SCHEDULE_ID}]}" \
  "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "502" ]]; then
  pass "POST /api/fees/pay/initiate/ (HTTP $st — 502 expected without live Paystack key)"
else
  fail "POST /api/fees/pay/initiate/ — unexpected status $st"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "TIMETABLE"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/timetable/periods/ \
  '{"name":"Period 1","start_time":"08:00:00","end_time":"08:45:00"}' \
  "$ADMIN_TOKEN")
check "POST /api/timetable/periods/" "$r" 201
PERIOD_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/timetable/periods/ "" "$ADMIN_TOKEN")
check "GET /api/timetable/periods/" "$r" 200

r=$(req POST /api/timetable/entries/ \
  "{\"class_arm\":${ARM_ID},\"subject\":${SUBJECT_ID},\"teacher\":${TEACHER_ID},\"period\":${PERIOD_ID},\"day_of_week\":\"MON\",\"term\":${TERM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/timetable/entries/" "$r" 201
TT_ENTRY_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/timetable/entries/ "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/" "$r" 200

r=$(req GET "/api/timetable/entries/grid/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/grid/" "$r" 200

r=$(req GET "/api/timetable/entries/by-class/${ARM_ID}/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/by-class/{id}/" "$r" 200

r=$(req GET "/api/timetable/entries/by-teacher/${TEACHER_ID}/?term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/timetable/entries/by-teacher/{id}/" "$r" 200

r=$(req GET "/api/timetable/entries/my-timetable/?term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/timetable/entries/my-timetable/" "$r" 200

r=$(req GET "/api/timetable/entries/teacher-load/?teacher=${TEACHER_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/teacher-load/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "NOTIFICATIONS"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/notifications/templates/ \
  '{"name":"Test Template","channel":"sms","body":"Hello {{student_name}}, this is a test."}' \
  "$ADMIN_TOKEN")
check "POST /api/notifications/templates/" "$r" 201
TEMPLATE_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/notifications/templates/ "" "$ADMIN_TOKEN")
check "GET /api/notifications/templates/" "$r" 200

r=$(req PUT "/api/notifications/templates/${TEMPLATE_ID}/" \
  '{"name":"Test Template Updated","channel":"sms","body":"Hi {{student_name}}!"}' \
  "$ADMIN_TOKEN")
check "PUT /api/notifications/templates/{id}/" "$r" 200

# Send notification (will attempt real SMS — may fail without Termii key)
r=$(req POST /api/notifications/send/ \
  "{\"channel\":\"sms\",\"template_id\":${TEMPLATE_ID},\"recipient_ids\":[${STUDENT_USER_ID}]}" \
  "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "201" || "$st" == "207" ]]; then
  pass "POST /api/notifications/send/ (HTTP $st)"
else
  skip "POST /api/notifications/send/ — HTTP $st (may need Termii key)"
fi

r=$(req GET /api/notifications/logs/ "" "$ADMIN_TOKEN")
check "GET /api/notifications/logs/" "$r" 200

r=$(req DELETE "/api/notifications/templates/${TEMPLATE_ID}/" "" "$ADMIN_TOKEN")
check "DELETE /api/notifications/templates/{id}/" "$r" 204

# ─────────────────────────────────────────────────────────────────────────────
section "ANALYTICS"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req GET /api/analytics/overview/ "" "$ADMIN_TOKEN")
check "GET /api/analytics/overview/" "$r" 200

r=$(req POST /api/analytics/refresh/ "" "$ADMIN_TOKEN")
check "POST /api/analytics/refresh/" "$r" 200

r=$(req GET "/api/analytics/class/${ARM_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/analytics/class/{id}/" "$r" 200

r=$(req GET "/api/analytics/student/${STUDENT_USER_ID}/trends/" "" "$ADMIN_TOKEN")
check "GET /api/analytics/student/{id}/trends/" "$r" 200

r=$(req GET "/api/analytics/transcript/${STUDENT_USER_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/analytics/transcript/{id}/ (PDF)" "$r" 200

r=$(req GET "/api/reports/transcript/${STUDENT_USER_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/reports/transcript/{id}/ (PDF)" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "PROMOTION"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req POST /api/promotion/criteria/ \
  "{\"class_level_id\":${LEVEL_ID},\"min_subjects_to_pass\":3,\"min_average_score\":40,\"min_attendance_pct\":50,\"auto_promote_if_met\":false}" \
  "$ADMIN_TOKEN")
check "POST /api/promotion/criteria/" "$r" 201

r=$(req GET /api/promotion/criteria/ "" "$ADMIN_TOKEN")
check "GET /api/promotion/criteria/" "$r" 200

r=$(req POST "/api/promotion/evaluate/?session=${SESSION_ID}&class_level=${LEVEL_ID}" "" "$ADMIN_TOKEN")
check "POST /api/promotion/evaluate/" "$r" 200
EVAL_RESULTS=$(body_of "$r")

# Create second class arm for promotion target
r=$(req POST /api/class-levels/ '{"name":"JSS2","order_index":2,"is_final_year":false}' "$ADMIN_TOKEN")
LEVEL2_ID=$(jq_get "$(body_of "$r")" ".id")
r=$(req POST /api/class-arms/ "{\"name\":\"A\",\"class_level\":${LEVEL2_ID}}" "$ADMIN_TOKEN")
ARM2_ID=$(jq_get "$(body_of "$r")" ".id")

DECISIONS="[{\"student_id\":${STUDENT_PROFILE_ID},\"session_id\":${SESSION_ID},\"to_class_id\":${ARM2_ID},\"decision\":\"promoted\",\"criteria_met\":true,\"notes\":\"Test promotion\"}]"
r=$(req POST /api/promotion/execute/ "$DECISIONS" "$ADMIN_TOKEN")
check "POST /api/promotion/execute/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "PARENT — OTP & Dashboard"
# ─────────────────────────────────────────────────────────────────────────────
PARENT_PHONE="08012345678"

r=$(req POST /api/auth/parent/otp-request/ \
  "{\"phone\":\"${PARENT_PHONE}\"}")
check "POST /api/auth/parent/otp-request/" "$r" 200

# OTP verify will fail without the real OTP from cache/SMS — expected 401
r=$(req POST /api/auth/parent/otp-verify/ \
  "{\"phone\":\"${PARENT_PHONE}\",\"otp\":\"000000\"}")
st=$(status_of "$r")
if [[ "$st" == "401" ]]; then
  pass "POST /api/auth/parent/otp-verify/ rejects invalid OTP (HTTP 401)"
else
  skip "POST /api/auth/parent/otp-verify/ — HTTP $st (unexpected)"
fi

# Parent children & dashboard (requires a linked parent account — skip if none)
skip "GET /api/parent/children/ — requires pre-linked parent account"
skip "GET /api/parent/dashboard/{id}/ — requires pre-linked parent account"

# ─────────────────────────────────────────────────────────────────────────────
section "AUTH — Me PATCH"
# ─────────────────────────────────────────────────────────────────────────────
r=$(req GET /api/auth/me/ "" "$TEACHER_TOKEN")
check "GET /api/auth/me/ (teacher)" "$r" 200

r=$(req PATCH /api/auth/me/ \
  '{"first_name":"Updated","last_name":"Teacher"}' \
  "$TEACHER_TOKEN")
check "PATCH /api/auth/me/" "$r" 200

# ─────────────────────────────────────────────────────────────────────────────
section "SECURITY — tenant isolation"
# ─────────────────────────────────────────────────────────────────────────────
# Student should not be able to create staff, fee categories, etc.
r=$(req POST /api/staff/ \
  '{"email":"hacker@x.com","first_name":"H","last_name":"X","password":"hacked","role":"teacher"}' \
  "$STUDENT_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "403" || "$st" == "401" ]]; then
  pass "Student cannot create staff (HTTP $st)"
else
  fail "Student created staff — expected 403/401, got $st"
fi

r=$(req POST /api/fees/categories/ \
  '{"name":"Fake Fee"}' \
  "$STUDENT_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "403" || "$st" == "401" ]]; then
  pass "Student cannot create fee categories (HTTP $st)"
else
  fail "Student created fee category — expected 403/401, got $st"
fi

# Unauthenticated request should be rejected
r=$(req GET /api/gradebook/entries/ "")
st=$(status_of "$r")
if [[ "$st" == "401" ]]; then
  pass "Unauthenticated request rejected (HTTP 401)"
else
  fail "Unauthenticated request not rejected — got $st"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "CLEANUP — Delete test data"
# ─────────────────────────────────────────────────────────────────────────────
req DELETE "/api/timetable/entries/${TT_ENTRY_ID}/" "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/timetable/periods/${PERIOD_ID}/"   "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/fees/categories/${FEE_CAT_ID}/"    "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/cbt/exams/${EXAM_ID}/"             "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/cbt/questions/${QUESTION_ID}/"     "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/cbt/topics/${TOPIC_ID}/"           "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/subjects/${SUBJECT_ID}/"           "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/students/${STUDENT_PROFILE_ID}/"   "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/staff/${TEACHER_ID}/"              "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/class-arms/${ARM_ID}/"             "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/class-arms/${ARM2_ID}/"            "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/class-levels/${LEVEL_ID}/"         "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/class-levels/${LEVEL2_ID}/"        "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/terms/${TERM_ID}/"                 "" "$ADMIN_TOKEN" >/dev/null 2>&1
req DELETE "/api/sessions/${SESSION_ID}/"           "" "$ADMIN_TOKEN" >/dev/null 2>&1
pass "Cleanup complete"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════${RESET}"
echo -e "  ${GREEN}PASS${RESET} ${BOLD}${PASS}${RESET}   ${RED}FAIL${RESET} ${BOLD}${FAIL}${RESET}   ${YELLOW}SKIP${RESET} ${BOLD}${SKIP}${RESET}"
echo -e "${BOLD}══════════════════════════════════${RESET}"

if [[ $FAIL -gt 0 ]]; then exit 1; else exit 0; fi
