section "RESULTS"

r=$(req POST "/api/results/positions/compute/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "POST /api/results/positions/compute/" "$r" 200

r=$(req GET "/api/results/class-results/?class_arm=${ARM_ID}&term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/results/class-results/" "$r" 200

r=$(req GET "/api/results/remarks/${STUDENT_USER_ID}/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/results/remarks/{student_id}/" "$r" 200

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
