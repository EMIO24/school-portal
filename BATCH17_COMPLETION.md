# Batch 17 — Academic Standards, Curriculum Intelligence & Continuity

## Status

**Implementation complete; final post-cleanup regression gate pending.**

Batch 17 establishes Paideia's academic-standard and continuity layer without replacing the existing session Scheme of Work, timetable, lesson-delivery evidence, assessment, or results systems.

## Delivered

### Curriculum provenance and applicability
- School-scoped curriculum sources and versions.
- Session/class/subject applicability pinned to a curriculum version.
- Historical execution cannot silently switch curriculum version after term execution exists.
- Required curriculum and school enrichment remain distinguishable.

### School academic standards
- Draft → submitted → reviewed → approved lifecycle.
- Approved standards are immutable historical records.
- New revisions clone approved content instead of mutating history.
- Topics, recommended weeks, objectives and source references are preserved.
- Approved standards can generate the selected term's Scheme of Work.
- Existing term schemes are never overwritten by standard generation.

### Lesson planning and institutional resources
- Teacher lesson plans are planning evidence, not proof of delivery.
- Academic resources support draft/review/approval and revision.
- Approved resources can be inherited and reused across sessions.
- Teacher drafts do not automatically become institutional standards.

### Academic management and continuity
- Principal/management read model separates planning from actual delivery.
- LessonRecord and TopicCoverage remain authoritative delivery evidence.
- Historical comparison uses the same term across academic sessions.
- Comparison is factual: planned topics, explicit coverage, recorded lesson outcomes, approved resources, curriculum version, approved standard revision and recorded result averages.
- No teacher-quality score or inferred teaching-performance rating is produced.

### High-volume input
Paideia's shared migration workflow now supports:
- classes and arms
- subjects
- students
- staff
- parents
- parent/student links
- teacher subject assignments
- opening balances
- timetable entries
- fee schedules
- academic-standard topics/objectives

Contextual Import actions are available from the relevant administration screens.

Teacher Score Entry also supports CSV template download and CSV import into the current **draft** score sheet. CSV import does not save, submit, approve or publish scores automatically.

Question Bank continues to support its existing document import workflow.

### Safety and audit boundaries
Generic bulk import is intentionally not enabled for:
- payment receipts
- LessonRecord delivery evidence
- published/approved result history

Those records remain protected by their existing transactional/audit workflows.

## Verification already achieved before final cleanup

- Backend Batch 17/regression gate: 36/36 tests passed.
- Frontend full gate: 48/48 suites and 326/326 tests passed.
- Production frontend build compiled successfully.
- Curriculum query count remained bounded as topic count grew.
- Principal operational query counts remained bounded as seeded data grew.

## Final post-cleanup gate

After the warning cleanup, contextual-import regression assertions and standard-to-scheme UI were added. The final gate must pass before this document's status is changed to **COMPLETE**:

```powershell
cd backend
python manage.py test enrollment.test_migration curriculum.test_batch17 curriculum.tests analytics.test_principal -v 1

cd ..\frontend
npm test -- --watchAll=false
npm run build
```

Test output is automatically written to `test-logs/backend-latest.txt` and `test-logs/frontend-latest.txt`.

## Deferred intentionally

The following belong to later roadmap batches or release hardening, not Batch 17:
- dedicated principal account role/permission model
- generative AI curriculum authoring
- teacher-quality scoring
- online school-fee payment execution and reconciliation
- communication automation
- multi-campus hierarchy and enterprise integrations

## Next roadmap batch

**Batch 18 — Online School-Fee Payments**
