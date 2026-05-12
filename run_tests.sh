#!/usr/bin/env bash
# run_tests.sh — master test runner for the school portal API
#
# Usage:
#   ./run_tests.sh
#   BASE_URL=https://your.railway.app SCHOOL_SLUG=myschool ./run_tests.sh
#
# Each numbered file in tests/ is sourced in order so they share state
# (tokens, IDs) without temp files.  Individual failures are counted but
# never abort the run unless they hit an explicit FATAL guard.
#
# Requires: curl, jq

set -euo pipefail
export PATH=$PATH:/c/Users/user/bin

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL="${BASE_URL:-http://localhost:8000}"
SCHOOL_SLUG="${SCHOOL_SLUG:-testschool}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@testschool.ng}"
ADMIN_PASS="${ADMIN_PASS:-AdminStr0ng#1}"
RUN_ID="${RUN_ID:-$(date +%s)}"
TEACHER_EMAIL="${TEACHER_EMAIL:-teacher.${RUN_ID}@testschool.ng}"
TEACHER_PASS="${TEACHER_PASS:-teacher1234}"
STUDENT_EMAIL="${STUDENT_EMAIL:-student.${RUN_ID}@testschool.ng}"
STUDENT_PASS="${STUDENT_PASS:-student1234}"

# ── Shared state — populated by individual test files ─────────────────────────

ADMIN_TOKEN=""; REFRESH_TOKEN=""
TEACHER_TOKEN=""; STUDENT_TOKEN=""
SCHOOL_ID=""
SESSION_ID=""; TERM_ID=""; HOLIDAY_ID=""
LEVEL_ID=""; LEVEL2_ID=""
ARM_ID=""; ARM2_ID=""
SUBJECT_ID=""
TEACHER_ID=""; TEACHER_STAFF_ID=""
STUDENT_PROFILE_ID=""; STUDENT_USER_ID=""; STUDENT_ADM_NUM=""
ATT_SESSION_ID=""
TOPIC_ID=""; QUESTION_ID=""; EXAM_ID=""
FEE_CAT_ID=""; FEE_SCHEDULE_ID=""; PAYMENT_ID=""
PERIOD_ID=""; TT_ENTRY_ID=""
TEMPLATE_ID=""
CARD_PIN=""; CARD_SERIAL=""; BATCH_LABEL=""

PASS=0; FAIL=0; SKIP=0

# ── Load shared helpers ────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/common.sh
source "$DIR/tests/common.sh"

# ── Run each test file in order ───────────────────────────────────────────────

TESTS=(
  01_health
  02_auth
  03_tenant
  04_cleanup
  05_academics
  06_enrollment
  07_attendance
  08_gradebook
  09_results
  10_scratch_cards
  11_cbt
  12_fees
  13_timetable
  14_notifications
  15_analytics
  16_promotion
  17_parent
  18_security
  19_cleanup
)

for t in "${TESTS[@]}"; do
  # shellcheck source=/dev/null
  source "$DIR/tests/${t}.sh"
done

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}══════════════════════════════════${RESET}"
echo -e "  ${GREEN}PASS${RESET} ${BOLD}${PASS}${RESET}   ${RED}FAIL${RESET} ${BOLD}${FAIL}${RESET}   ${YELLOW}SKIP${RESET} ${BOLD}${SKIP}${RESET}"
echo -e "${BOLD}══════════════════════════════════${RESET}"

[[ $FAIL -gt 0 ]] && exit 1 || exit 0
