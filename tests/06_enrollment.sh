section "ENROLLMENT — Class Levels"

r=$(req POST /api/class-levels/ \
  '{"name":"JSS1","order_index":1,"is_final_year":false}' \
  "$ADMIN_TOKEN")
check "POST /api/class-levels/" "$r" 201
LEVEL_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/class-levels/ "" "$ADMIN_TOKEN")
check "GET /api/class-levels/" "$r" 200

# ── Class Arms ─────────────────────────────────────────────────────────────

section "ENROLLMENT — Class Arms"

r=$(req POST /api/class-arms/ \
  "{\"name\":\"A\",\"class_level\":${LEVEL_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/class-arms/" "$r" 201
ARM_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/class-arms/ "" "$ADMIN_TOKEN")
check "GET /api/class-arms/" "$r" 200

# ── Subjects ───────────────────────────────────────────────────────────────

section "ENROLLMENT — Subjects"

r=$(req POST /api/subjects/ \
  "{\"name\":\"Mathematics\",\"code\":\"MTH\",\"class_level\":${LEVEL_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/subjects/" "$r" 201
SUBJECT_ID=$(jq_get "$(body_of "$r")" ".id")

r=$(req GET /api/subjects/ "" "$ADMIN_TOKEN")
check "GET /api/subjects/" "$r" 200

r=$(req GET "/api/subjects/by-class/${ARM_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/subjects/by-class/{arm_id}/" "$r" 200

# ── Staff ──────────────────────────────────────────────────────────────────

section "ENROLLMENT — Staff"

r=$(req POST /api/staff/ \
  "{\"new_email\":\"${TEACHER_EMAIL}\",\"new_first_name\":\"Test\",\"new_last_name\":\"Teacher\",\"new_role\":\"teacher\"}" \
  "$ADMIN_TOKEN")
check "POST /api/staff/ (create teacher)" "$r" 201
TEACHER_ID=$(jq_get "$(body_of "$r")" ".id")
TEACHER_USER_ID=$(jq_get "$(body_of "$r")" ".user")
TEACHER_STAFF_ID=$(jq_get "$(body_of "$r")" ".staff_id")

r=$(req GET /api/staff/ "" "$ADMIN_TOKEN")
check "GET /api/staff/" "$r" 200

r=$(req POST /api/subject-assignments/ \
  "{\"teacher\":${TEACHER_ID},\"subject\":${SUBJECT_ID},\"class_arm\":${ARM_ID},\"session\":${SESSION_ID},\"term\":${TERM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/subject-assignments/" "$r" 201

r=$(req POST /api/auth/login/ "{\"email\":\"${TEACHER_EMAIL}\",\"password\":\"${TEACHER_STAFF_ID}\"}")
check "POST /api/auth/login/ (teacher)" "$r" 200
TEACHER_TOKEN=$(jq_get "$(body_of "$r")" ".access")

# ── Students ───────────────────────────────────────────────────────────────

section "ENROLLMENT — Students"

r=$(req POST /api/students/ \
  "{\"new_email\":\"${STUDENT_EMAIL}\",\"new_first_name\":\"Test\",\"new_last_name\":\"Student\",\"current_class\":${ARM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/students/ (create student)" "$r" 201
STUDENT_PROFILE_ID=$(jq_get "$(body_of "$r")" ".id")
STUDENT_USER_ID=$(jq_get "$(body_of "$r")" ".user")
STUDENT_ADM_NUM=$(jq_get "$(body_of "$r")" ".admission_number")

r=$(req GET /api/students/ "" "$ADMIN_TOKEN")
check "GET /api/students/" "$r" 200

r=$(req GET "/api/students/by-class/${ARM_ID}/" "" "$ADMIN_TOKEN")
check "GET /api/students/by-class/{arm_id}/" "$r" 200

r=$(req POST "/api/students/${STUDENT_PROFILE_ID}/assign-class/" \
  "{\"class_arm\":${ARM_ID}}" \
  "$ADMIN_TOKEN")
check "POST /api/students/{id}/assign-class/" "$r" 200

r=$(req POST /api/auth/login/ "{\"email\":\"${STUDENT_EMAIL}\",\"password\":\"${STUDENT_ADM_NUM}\"}")
check "POST /api/auth/login/ (student)" "$r" 200
STUDENT_TOKEN=$(jq_get "$(body_of "$r")" ".access")

# ── Subject Assignments ────────────────────────────────────────────────────

section "ENROLLMENT — Subject Assignments"

r=$(req GET /api/subject-assignments/ "" "$ADMIN_TOKEN")
check "GET /api/subject-assignments/" "$r" 200

r=$(req GET "/api/subject-assignments/grid/?term=${TERM_ID}" "" "$ADMIN_TOKEN")
check "GET /api/subject-assignments/grid/" "$r" 200
