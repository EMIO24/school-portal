section "SCRATCH CARDS"

r=$(req POST /api/scratch-cards/generate/ \
  "{\"term_id\":${TERM_ID},\"quantity\":5,\"batch_name\":\"TEST-BATCH-01\"}" \
  "$ADMIN_TOKEN")
check "POST /api/scratch-cards/generate/" "$r" 200
BATCH_LABEL="TEST-BATCH-01"
GEN_CSV=$(body_of "$r")
CARD_SERIAL=$(printf '%s\n' "$GEN_CSV" | sed -n '2p' | cut -d',' -f1 | tr -d '\r')
CARD_PIN=$(printf '%s\n' "$GEN_CSV" | sed -n '2p' | cut -d',' -f2 | tr -d '\r')

r=$(req GET /api/scratch-cards/ "" "$ADMIN_TOKEN")
check "GET /api/scratch-cards/" "$r" 200

r=$(req GET /api/scratch-cards/batch-stats/ "" "$ADMIN_TOKEN")
check "GET /api/scratch-cards/batch-stats/" "$r" 200

r=$(req GET "/api/scratch-cards/unused-csv/?batch=${BATCH_LABEL}" "" "$ADMIN_TOKEN")
check "GET /api/scratch-cards/unused-csv/" "$r" 200

if [[ -n "$CARD_PIN" && "$CARD_PIN" != "null" && -n "$CARD_SERIAL" && "$CARD_SERIAL" != "null" ]]; then
  r=$(req POST /api/results/check/ \
    "{\"serial_number\":\"${CARD_SERIAL}\",\"pin\":\"${CARD_PIN}\",\"admission_number\":\"${STUDENT_ADM_NUM}\"}")
  check "POST /api/results/check/ (public scratch-card)" "$r" 200
else
  skip "POST /api/results/check/ — could not extract card PIN/serial"
fi
