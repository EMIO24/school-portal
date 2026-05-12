section "PRE-RUN CLEANUP — remove leftover data from previous runs"
# All deletions are silent. _cleanup uses serial GET→DELETE (no process
# substitution) so /tmp/_body is never shared across concurrent calls.

# Sessions first — CASCADE wipes terms → holidays, subject_assignments,
# gradebook, attendance, fee schedules, scratch cards, result remarks,
# CBT exams/sessions, and timetable entries in one shot.
_cleanup "/api/sessions/"    'select(.name == "2024/2025") | .id'

# Subjects (CASCADE → subject_assignment M2M rows)
_cleanup "/api/subjects/"    'select(.code == "MTH") | .id'

# Class arms before class levels (FK order)
_cleanup "/api/class-arms/"  'select(.name == "A") | .id'
_cleanup "/api/class-levels/" 'select(.name == "JSS1" or .name == "JSS2") | .id'

# Students and staff (user CASCADE deletes profiles)
_cleanup "/api/students/"    "select(.email == \"${STUDENT_EMAIL}\") | .id"
_cleanup "/api/staff/"       "select(.email == \"${TEACHER_EMAIL}\") | .id"

# Ancillary resources
_cleanup "/api/fees/categories/"          'select(.name | startswith("School Fees")) | .id'
_cleanup "/api/notifications/templates/"  'select(.name | startswith("Test Template")) | .id'
_cleanup "/api/timetable/periods/"        'select(.name == "Period 1") | .id'

pass "Pre-run cleanup complete"
