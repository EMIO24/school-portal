section "GRADEBOOK — Grade Scale & Score Entry"

r=$(req GET /api/gradebook/entries/grade-scale/ "" "$TEACHER_TOKEN")
check "GET /api/gradebook/entries/grade-scale/" "$r" 200

r=$(req GET "/api/gradebook/entries/?class_arm=${ARM_ID}&subject=${SUBJECT_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "GET /api/gradebook/entries/ (filtered)" "$r" 200

SCORES="[{\"student_id\":${STUDENT_USER_ID},\"first_test\":10,\"second_test\":10,\"assignment\":5,\"project\":5,\"practical\":0,\"exam_score\":50}]"
r=$(req POST /api/gradebook/entries/bulk-update/ \
  "{\"class_arm\":${ARM_ID},\"subject\":${SUBJECT_ID},\"term\":${TERM_ID},\"session\":${SESSION_ID},\"scores\":${SCORES}}" \
  "$TEACHER_TOKEN")
check "POST /api/gradebook/entries/bulk-update/" "$r" 200

r=$(req POST "/api/gradebook/entries/publish/?class_arm=${ARM_ID}&subject=${SUBJECT_ID}&term=${TERM_ID}" "" "$TEACHER_TOKEN")
check "POST /api/gradebook/entries/publish/" "$r" 200

# ── Affective & Psychomotor ────────────────────────────────────────────────

section "GRADEBOOK — Affective & Psychomotor Domains"

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
