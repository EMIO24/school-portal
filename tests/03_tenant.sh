section "TENANT — School"

r=$(req GET /api/school/me/ "" "$ADMIN_TOKEN")
check "GET /api/school/me/" "$r" 200
SCHOOL_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/schools/ "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "403" ]]; then
  pass "GET /api/schools/ (HTTP $st — 403 for school_admin, 200 for superadmin)"
else
  fail "GET /api/schools/ — unexpected $st"
fi
