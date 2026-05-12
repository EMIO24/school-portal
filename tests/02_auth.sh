section "AUTH — Admin login"

r=$(req POST /api/auth/login/ "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASS}\"}")
check "POST /api/auth/login/ (admin)" "$r" 200
body=$(body_of "$r")
ADMIN_TOKEN=$(jq_get "$body" ".access")
REFRESH_TOKEN=$(jq_get "$body" ".refresh")

if [[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]]; then
  echo -e "${RED}FATAL: Admin login failed — cannot continue. Check ADMIN_EMAIL/ADMIN_PASS.${RESET}"
  exit 1
fi

r=$(req POST /api/auth/login/ '{"email":"wrong@x.com","password":"badpass"}')
check "POST /api/auth/login/ rejects bad credentials" "$r" 401

r=$(req POST /api/auth/token/refresh/ "{\"refresh\":\"${REFRESH_TOKEN}\"}")
check "POST /api/auth/token/refresh/" "$r" 200
NEW_ACCESS=$(jq_get "$(body_of "$r")" ".access")
[[ -n "$NEW_ACCESS" && "$NEW_ACCESS" != "null" ]] && ADMIN_TOKEN="$NEW_ACCESS"

r=$(req GET /api/auth/me/ "" "$ADMIN_TOKEN")
check "GET /api/auth/me/" "$r" 200

TMP_PASS="TmpT3st@Pass99"
r=$(req POST /api/auth/change-password/ \
  "{\"current_password\":\"${ADMIN_PASS}\",\"new_password\":\"${TMP_PASS}\",\"confirm_password\":\"${TMP_PASS}\"}" \
  "$ADMIN_TOKEN")
check "POST /api/auth/change-password/" "$r" 200

r=$(req POST /api/auth/login/ "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${TMP_PASS}\"}")
TMP_TOKEN=$(jq_get "$(body_of "$r")" ".access")
r=$(req POST /api/auth/change-password/ \
  "{\"current_password\":\"${TMP_PASS}\",\"new_password\":\"${ADMIN_PASS}\",\"confirm_password\":\"${ADMIN_PASS}\"}" \
  "$TMP_TOKEN")
check "POST /api/auth/change-password/ (restore)" "$r" 200

r=$(req POST /api/auth/login/ "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASS}\"}")
body=$(body_of "$r")
ADMIN_TOKEN=$(jq_get "$body" ".access")
if [[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]]; then
  echo -e "${RED}FATAL: Could not re-login after password restore.${RESET}"
  exit 1
fi
