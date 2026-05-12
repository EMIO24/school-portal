section "CBT — Topics & Questions"

r=$(req POST /api/cbt/topics/ \
  "{\"name\":\"Algebra Basics\",\"subject\":${SUBJECT_ID},\"class_level\":${LEVEL_ID}}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/topics/" "$r" 201
TOPIC_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/cbt/topics/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/topics/" "$r" 200

r=$(req POST /api/cbt/questions/ \
  "{\"topic\":${TOPIC_ID},\"subject\":${SUBJECT_ID},\"class_level\":${LEVEL_ID},\"question_text\":\"What is 2+2?\",\"question_type\":\"mcq\",\"difficulty\":\"easy\",\"cognitive_level\":\"knowledge\",\"options\":[{\"id\":\"A\",\"text\":\"3\"},{\"id\":\"B\",\"text\":\"4\"},{\"id\":\"C\",\"text\":\"5\"},{\"id\":\"D\",\"text\":\"6\"}],\"correct_answer\":\"B\",\"explanation\":\"2 plus 2 equals 4.\",\"is_active\":true}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/questions/ (MCQ)" "$r" 201
QUESTION_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req POST /api/cbt/questions/ \
  "{\"topic\":${TOPIC_ID},\"subject\":${SUBJECT_ID},\"class_level\":${LEVEL_ID},\"question_text\":\"The capital of Nigeria is ___.\",\"question_type\":\"fill_blank\",\"difficulty\":\"easy\",\"cognitive_level\":\"knowledge\",\"options\":[],\"correct_answer\":\"Abuja\",\"explanation\":\"Abuja is Nigeria's capital city.\",\"is_active\":true}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/questions/ (fill_blank)" "$r" 201

r=$(req GET /api/cbt/questions/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/questions/" "$r" 200

r=$(req GET /api/cbt/questions/stats/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/questions/stats/" "$r" 200

BULK_Q='[{"topic":'${TOPIC_ID}',"subject":'${SUBJECT_ID}',"class_level":'${LEVEL_ID}',"question_text":"5 x 5 = ?","question_type":"mcq","difficulty":"easy","cognitive_level":"knowledge","options":[{"id":"A","text":"20"},{"id":"B","text":"25"},{"id":"C","text":"30"},{"id":"D","text":"35"}],"correct_answer":"B","is_active":true}]'
r=$(req POST /api/cbt/questions/bulk-import/ "$BULK_Q" "$TEACHER_TOKEN")
check "POST /api/cbt/questions/bulk-import/" "$r" 201

# ── Exams ──────────────────────────────────────────────────────────────────

section "CBT — Exams"

START_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
END_TS=$(date -u -d "+2 hours" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
  python3 -c "from datetime import datetime,timedelta; print((datetime.utcnow()+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ'))")

r=$(req POST /api/cbt/exams/ \
  "{\"title\":\"Test Maths Exam\",\"subject\":${SUBJECT_ID},\"term\":${TERM_ID},\"session\":${SESSION_ID},\"class_arms\":[${ARM_ID}],\"duration_minutes\":60,\"start_datetime\":\"${START_TS}\",\"end_datetime\":\"${END_TS}\",\"instructions\":\"Answer all questions.\",\"selection_mode\":\"manual\",\"manual_questions\":[${QUESTION_ID}],\"random_config\":[],\"randomize_questions\":false,\"randomize_options\":false,\"allow_review\":true,\"show_score_immediately\":true,\"status\":\"published\"}" \
  "$TEACHER_TOKEN")
check "POST /api/cbt/exams/" "$r" 201
EXAM_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/cbt/exams/ "" "$TEACHER_TOKEN")
check "GET /api/cbt/exams/" "$r" 200

r=$(req GET "/api/cbt/exams/${EXAM_ID}/" "" "$TEACHER_TOKEN")
check "GET /api/cbt/exams/{id}/" "$r" 200

r=$(req GET /api/cbt/exams/available/ "" "$STUDENT_TOKEN")
check "GET /api/cbt/exams/available/ (student)" "$r" 200

r=$(req POST "/api/cbt/exams/${EXAM_ID}/start/" "" "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/start/" "$r" 200

r=$(req GET "/api/cbt/exams/${EXAM_ID}/status/" "" "$STUDENT_TOKEN")
check "GET /api/cbt/exams/{id}/status/" "$r" 200

r=$(req POST "/api/cbt/exams/${EXAM_ID}/save-answer/" \
  "{\"question_id\":${QUESTION_ID},\"selected_option\":\"B\"}" \
  "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/save-answer/" "$r" 200

r=$(req POST "/api/cbt/exams/${EXAM_ID}/log-tab-switch/" "" "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/log-tab-switch/" "$r" 200

r=$(req POST "/api/cbt/exams/${EXAM_ID}/submit/" "" "$STUDENT_TOKEN")
check "POST /api/cbt/exams/{id}/submit/" "$r" 200
