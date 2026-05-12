section "CLEANUP — Delete test data"
# Delete in dependency order so FK constraints don't block.
# All calls redirect to /dev/null — failures are intentionally silent.

req DELETE "/api/timetable/entries/${TT_ENTRY_ID}/" "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/timetable/periods/${PERIOD_ID}/"   "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/fees/categories/${FEE_CAT_ID}/"    "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/cbt/exams/${EXAM_ID}/"             "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/cbt/questions/${QUESTION_ID}/"     "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/cbt/topics/${TOPIC_ID}/"           "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/subjects/${SUBJECT_ID}/"           "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/students/${STUDENT_PROFILE_ID}/"   "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/staff/${TEACHER_ID}/"              "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/class-arms/${ARM_ID}/"             "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/class-arms/${ARM2_ID}/"            "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/class-levels/${LEVEL_ID}/"         "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/class-levels/${LEVEL2_ID}/"        "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/terms/${TERM_ID}/"                 "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true
req DELETE "/api/sessions/${SESSION_ID}/"           "" "$ADMIN_TOKEN" >/dev/null 2>&1 || true

pass "Cleanup complete"
