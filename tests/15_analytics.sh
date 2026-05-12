section "ANALYTICS"

r=$(req GET /api/analytics/overview/ "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "204" ]]; then
  pass "GET /api/analytics/overview/ (HTTP $st)"
else
  fail "GET /api/analytics/overview/ — expected 200/204, got $st"
fi

r=$(req POST /api/analytics/refresh/ "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "202" ]]; then
  pass "POST /api/analytics/refresh/ (HTTP $st)"
else
  fail "POST /api/analytics/refresh/ — expected 200/202, got $st"
fi

r=$(req GET "/api/analytics/class/${ARM_ID}/" "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "204" || "$st" == "404" ]]; then
  pass "GET /api/analytics/class/{id}/ (HTTP $st)"
else
  fail "GET /api/analytics/class/{id}/ — expected 200/204/404, got $st"
fi

r=$(req GET "/api/analytics/student/${STUDENT_USER_ID}/trends/" "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "204" || "$st" == "404" ]]; then
  pass "GET /api/analytics/student/{id}/trends/ (HTTP $st)"
else
  fail "GET /api/analytics/student/{id}/trends/ — expected 200/204/404, got $st"
fi

r=$(req GET "/api/analytics/transcript/${STUDENT_USER_ID}/" "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "404" ]]; then
  pass "GET /api/analytics/transcript/{id}/ (HTTP $st)"
else
  fail "GET /api/analytics/transcript/{id}/ — expected 200/404, got $st"
fi

r=$(req GET "/api/reports/transcript/${STUDENT_USER_ID}/" "" "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "404" ]]; then
  pass "GET /api/reports/transcript/{id}/ (HTTP $st)"
else
  fail "GET /api/reports/transcript/{id}/ — expected 200/404, got $st"
fi
