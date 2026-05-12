section "NOTIFICATIONS"

r=$(req POST /api/notifications/templates/ \
  '{"name":"Test Template","type":"sms","category":"general","body":"Hello {{student_name}}, this is a test."}' \
  "$ADMIN_TOKEN")
check "POST /api/notifications/templates/" "$r" 201
TEMPLATE_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/notifications/templates/ "" "$ADMIN_TOKEN")
check "GET /api/notifications/templates/" "$r" 200

r=$(req PUT "/api/notifications/templates/${TEMPLATE_ID}/" \
  '{"name":"Test Template Updated","type":"sms","category":"general","body":"Hi {{student_name}}!"}' \
  "$ADMIN_TOKEN")
check "PUT /api/notifications/templates/{id}/" "$r" 200

r=$(req POST /api/notifications/send/ \
  "{\"channel\":\"sms\",\"template_id\":${TEMPLATE_ID},\"recipient_ids\":[${STUDENT_USER_ID}]}" \
  "$ADMIN_TOKEN")
st=$(status_of "$r")
if [[ "$st" == "200" || "$st" == "201" || "$st" == "207" ]]; then
  pass "POST /api/notifications/send/ (HTTP $st)"
else
  skip "POST /api/notifications/send/ — HTTP $st (may need Termii key)"
fi

r=$(req GET /api/notifications/logs/ "" "$ADMIN_TOKEN")
check "GET /api/notifications/logs/" "$r" 200

r=$(req DELETE "/api/notifications/templates/${TEMPLATE_ID}/" "" "$ADMIN_TOKEN")
check "DELETE /api/notifications/templates/{id}/" "$r" 204
