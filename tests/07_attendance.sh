section "ATTENDANCE"

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

RECORDS="[{\"student_id\":${STUDENT_USER_ID},\"status\":\"present\"}]"
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
