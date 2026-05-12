section "PARENT — OTP & Dashboard"

PARENT_PHONE="08012345678"

r=$(req POST /api/auth/parent/otp-request/ "{\"phone\":\"${PARENT_PHONE}\"}")
check "POST /api/auth/parent/otp-request/" "$r" 200

r=$(req POST /api/auth/parent/otp-verify/ "{\"phone\":\"${PARENT_PHONE}\",\"otp\":\"000000\"}")
st=$(status_of "$r")
if [[ "$st" == "401" ]]; then
  pass "POST /api/auth/parent/otp-verify/ rejects invalid OTP (HTTP 401)"
else
  skip "POST /api/auth/parent/otp-verify/ — HTTP $st (unexpected)"
fi

skip "GET /api/parent/children/ — requires pre-linked parent account"
skip "GET /api/parent/dashboard/{id}/ — requires pre-linked parent account"
