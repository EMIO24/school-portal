section "PROMOTION"

r=$(req POST /api/promotion/criteria/ \
  "{\"class_level_id\":${LEVEL_ID},\"min_subjects_to_pass\":3,\"min_average_score\":40,\"min_attendance_pct\":50,\"auto_promote_if_met\":false}" \
  "$ADMIN_TOKEN")
check "POST /api/promotion/criteria/" "$r" 201

r=$(req GET /api/promotion/criteria/ "" "$ADMIN_TOKEN")
check "GET /api/promotion/criteria/" "$r" 200

r=$(req POST "/api/promotion/evaluate/?session=${SESSION_ID}&class_level=${LEVEL_ID}" "" "$ADMIN_TOKEN")
check "POST /api/promotion/evaluate/" "$r" 200

# Create JSS2 as the promotion target
r=$(req POST /api/class-levels/ '{"name":"JSS2","order_index":2,"is_final_year":false}' "$ADMIN_TOKEN")
LEVEL2_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req POST /api/class-arms/ "{\"name\":\"A\",\"class_level\":${LEVEL2_ID}}" "$ADMIN_TOKEN")
ARM2_ID=$(jq_get "$(body_of "$r")" ".id")

DECISIONS="[{\"student_id\":${STUDENT_PROFILE_ID},\"session_id\":${SESSION_ID},\"to_class_id\":${ARM2_ID},\"decision\":\"promoted\",\"criteria_met\":true,\"notes\":\"Test promotion\"}]"
r=$(req POST /api/promotion/execute/ "$DECISIONS" "$ADMIN_TOKEN")
check "POST /api/promotion/execute/" "$r" 200
