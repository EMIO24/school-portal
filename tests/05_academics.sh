section "ACADEMICS — Sessions"

r=$(req POST /api/sessions/ \
  '{"name":"2024/2025","start_date":"2024-09-01","end_date":"2025-07-31"}' \
  "$ADMIN_TOKEN")
check "POST /api/sessions/" "$r" 201
SESSION_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/sessions/ "" "$ADMIN_TOKEN")
check "GET /api/sessions/" "$r" 200

r=$(req GET "/api/sessions/${SESSION_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/sessions/{id}/" "$r" 200

r=$(req POST "/api/sessions/${SESSION_ID}/set-current/" "" "$ADMIN_TOKEN")
check "POST /api/sessions/{id}/set-current/" "$r" 200

# ── Terms ──────────────────────────────────────────────────────────────────

section "ACADEMICS — Terms"

r=$(req POST /api/terms/ \
  "{\"name\":\"first\",\"session\":${SESSION_ID},\"start_date\":\"2024-09-02\",\"end_date\":\"2024-12-13\"}" \
  "$ADMIN_TOKEN")
check "POST /api/terms/" "$r" 201
TERM_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/terms/ "" "$ADMIN_TOKEN")
check "GET /api/terms/" "$r" 200

r=$(req POST "/api/terms/${TERM_ID}/set-current/" "" "$ADMIN_TOKEN")
check "POST /api/terms/{id}/set-current/" "$r" 200

# ── Holidays & Calendar ────────────────────────────────────────────────────

section "ACADEMICS — Holidays & Calendar"

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
