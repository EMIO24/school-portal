section "HEALTH CHECK"

r=$(req GET /health/ "")
check "GET /health/" "$r" 200
