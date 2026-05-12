section "TIMETABLE"

r=$(req POST /api/timetable/periods/ \
  '{"name":"Period 1","start_time":"08:00:00","end_time":"08:45:00","order_index":1,"is_break":false}' \
  "$ADMIN_TOKEN")
check "POST /api/timetable/periods/" "$r" 201
PERIOD_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/timetable/periods/ "" "$ADMIN_TOKEN")
check "GET /api/timetable/periods/" "$r" 200

r=$(req POST /api/timetable/entries/ \
  "{\"class_arm\":${ARM_ID},\"subject\":${SUBJECT_ID},\"teacher\":${TEACHER_USER_ID},\"period\":${PERIOD_ID},\"day_of_week\":\"MON\",\"term\":${TERM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/timetable/entries/" "$r" 201
TT_ENTRY_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/timetable/entries/ "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/" "$r" 200

r=$(req GET "/api/timetable/entries/grid/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/grid/" "$r" 200

r=$(req GET "/api/timetable/entries/by-class/${ARM_ID}/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/by-class/{id}/" "$r" 200

r=$(req GET "/api/timetable/entries/by-teacher/${TEACHER_USER_ID}/?term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/timetable/entries/by-teacher/{id}/" "$r" 200

r=$(req GET "/api/timetable/entries/my-timetable/?term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/timetable/entries/my-timetable/" "$r" 200

r=$(req GET "/api/timetable/entries/teacher-load/?teacher=${TEACHER_USER_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/timetable/entries/teacher-load/" "$r" 200
