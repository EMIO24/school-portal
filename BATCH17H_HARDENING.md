# Batch 17H — Historical Integrity & Access Hardening

Status: **IMPLEMENTED — AWAITING REGRESSION CONFIRMATION**

Batch 17H was inserted after Batch 17 after a full-project regression scan found places where later capabilities had made older mutable setup records more consequential.

## 1. Teaching assignment history

- Historical SubjectAssignment rows cannot be deleted once operational academic history depends on their school/term/class/subject scope.
- Protected history includes gradebook scores, lesson records, lesson plans, online assignments and CBT exams.
- The guard is enforced in the API and by a pre-delete signal so QuerySet.delete(), Django admin or future scripts do not silently erase teaching responsibility.
- Intentional whole-school teardown remains possible for isolated tenant-reset workflows.
- Bulk teacher assignment replacement now refuses to remove protected rows and preserves unchanged assignments without colliding with uniqueness validation.

## 2. Fee schedule history

- A FeeSchedule with financial history cannot be rewritten through the fee setup endpoint.
- Model save() also blocks mutation of a used schedule, protecting future scripts/admin code from bypassing the API rule.
- Financial history includes FeePayment, StudentLedgerEntry and fee PaymentOrder allocations.
- Unused schedules remain editable.
- The Migration Centre already reuses exact schedules and rejects differing existing schedules.

## 3. Immutable receipt facts

FeePayment now captures receipt_snapshot at creation containing:

- school name/logo/motto/contact/registration number;
- document colours;
- student name/admission number/class;
- fee category;
- term/session;
- amount/date/method/reference;
- issuing staff name.

Receipt PDFs now render from the immutable snapshot rather than current mutable school, student, class or fee-category records.

Migration 0013 backfills existing receipts with a best-effort snapshot of their current state, freezing those records from the migration point forward.

## 4. Consistent active-teacher access

assigned_classes() now requires both:

- active StaffProfile employment status; and
- active user account.

This aligns attendance/domain access with the stricter assignment checks already used by gradebook, CBT, curriculum and lesson planning.

## 5. Staff privacy

Full staff list/retrieve/by-role endpoints are now limited to school administrators and teachers.

Students and parents no longer receive the internal staff directory, staff IDs, email addresses, specialization or employment-state data through those endpoints.

## 6. Timetable visibility

Timetable entry reads are now role scoped:

- school_admin: whole school;
- teacher: own timetable;
- student: current class;
- parent: linked active children's current classes;
- other roles: none.

teacher-load is school-admin only.

## Additional finance consistency found during 17H

Premium analytics fee collection now derives expected and paid amounts from immutable StudentLedgerEntry facts instead of live FeeSchedule values.

The administrator outstanding-fees report now derives charges, payments and balances from the ledger, so even an out-of-band schedule mutation cannot rewrite historical debtor figures.

## Regression tests added

- historical assignment API deletion blocked;
- historical assignment QuerySet deletion blocked;
- bulk replacement cannot remove historical assignment;
- unused assignment can still be corrected;
- suspended teacher has no assigned-classes helper access;
- students/parents cannot browse staff directory;
- used fee schedule cannot be changed through fee setup;
- used fee schedule cannot be changed by model save();
- unused fee schedule remains editable;
- outstanding-fees report remains based on frozen ledger facts;
- receipt snapshot survives later school/student/category edits;
- receipt PDF fallback uses snapshot facts;
- student timetable limited to own class;
- parent timetable limited to linked child;
- teacher timetable limited to own entries;
- teacher-load restricted to school admin.

## Deliberately deferred lifecycle work

Batch 17H does not attempt to solve historical student class membership through patches around StudentProfile.current_class.

Admissions, session enrollment history, promotion, graduation and rollover remain planned lifecycle work so assignments/results/attendance can eventually resolve historical class membership from a proper session-enrollment model.

## Infrastructure impact

None.

No Redis, Celery worker, Celery Beat, polling service or additional always-on service is required by Batch 17H.

Production branch remains untouched.
