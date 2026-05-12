section "AUTH — Profile Update"

r=$(req GET /api/auth/me/ "" "$TEACHER_TOKEN")
check "GET /api/auth/me/ (teacher)" "$r" 200

r=$(req PATCH /api/auth/me/ \
  '{"first_name":"Updated","last_name":"Teacher"}' \
  "$TEACHER_TOKEN")
check "PATCH /api/auth/me/" "$r" 200

# ── Security — tenant isolation ────────────────────────────────────────────

section "SECURITY — tenant isolation"

r=$(req POST /api/staff/ \
  '{"email":"hacker@x.com","first_name":"H","last_name":"X","password":"hacked","role":"teacher"}' \
  "$STUDENT_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "403" || "$st" == "401" ]]; then
  pass "Student cannot create staff (HTTP $st)"
else
  fail "Student created staff — expected 403/401, got $st"
fi

r=$(req POST /api/fees/categories/ '{"name":"Fake Fee"}' "$STUDENT_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "403" || "$st" == "401" ]]; then
  pass "Student cannot create fee categories (HTTP $st)"
else
  fail "Student created fee category — expected 403/401, got $st"
fi

r=$(req GET /api/gradebook/entries/ "")
st=$(status_of "$r")
if [[ "$st" == "401" ]]; then
  pass "Unauthenticated request rejected (HTTP 401)"
else
  fail "Unauthenticated request not rejected — got $st"
fi
