section "FEES — Categories & Schedules"

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

SCHEDULES="[{\"class_level_id\":${LEVEL_ID},\"fee_category_id\":${FEE_CAT_ID},\"amount\":25000,\"due_date\":\"2024-09-30\"}]"
r=$(req POST /api/fees/schedule/ \
  "{\"term_id\":${TERM_ID},\"schedules\":${SCHEDULES}}" \
  "$ADMIN_TOKEN")
check "POST /api/fees/schedule/ (bulk)" "$r" 201

r=$(req GET "/api/fees/schedule/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/schedule/" "$r" 200
FEE_SCHEDULE_ID=$(jq_get "$(body_of "$r")" ".[0].id")

r=$(req GET "/api/fees/student/${STUDENT_PROFILE_ID}/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/student/{id}/" "$r" 200

TODAY=$(date +%Y-%m-%d)
r=$(req POST /api/fees/pay/manual/ \
  "{\"student_id\":${STUDENT_PROFILE_ID},\"fee_schedule_id\":${FEE_SCHEDULE_ID},\"amount_paid\":25000,\"payment_date\":\"${TODAY}\",\"method\":\"cash\"}" \
  "$ADMIN_TOKEN")
check "POST /api/fees/pay/manual/" "$r" 201
PAYMENT_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET "/api/fees/receipts/${PAYMENT_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/fees/receipts/{id}/ (PDF)" "$r" 200

r=$(req GET "/api/fees/outstanding/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/outstanding/" "$r" 200

r=$(req GET "/api/fees/outstanding/?term=${TERM_ID}&class_arm=${ARM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/fees/outstanding/ (filtered by class_arm)" "$r" 200

r=$(req POST /api/fees/pay/initiate/ \
  "{\"student_id\":${STUDENT_PROFILE_ID},\"fee_schedule_ids\":[${FEE_SCHEDULE_ID}]}" \
  "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "502" ]]; then
  pass "POST /api/fees/pay/initiate/ (HTTP $st — 502 expected without live Paystack key)"
else
  fail "POST /api/fees/pay/initiate/ — unexpected status $st"
fi
