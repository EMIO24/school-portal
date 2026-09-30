def assignment_has_history(assignment):
    """Return True once operational academic records depend on this teaching scope."""
    from gradebook.models import ScoreEntry
    from timetable.models import LessonRecord
    from curriculum.models import LessonPlan
    from cbt.models import OnlineAssignment, CBTExam

    scope = {
        'school': assignment.school,
        'term': assignment.term,
        'class_arm': assignment.class_arm,
        'subject': assignment.subject,
    }
    if ScoreEntry.objects.filter(**scope).exists():
        return True
    if LessonPlan.objects.filter(**scope).exists():
        return True
    if OnlineAssignment.objects.filter(**scope).exists():
        return True
    if LessonRecord.objects.filter(
        school=assignment.school,
        term=assignment.term,
        class_arm_id_snapshot=assignment.class_arm_id,
        subject_id_snapshot=assignment.subject_id,
    ).exists():
        return True
    return CBTExam.objects.filter(
        school=assignment.school, term=assignment.term, subject=assignment.subject,
        class_arms=assignment.class_arm,
    ).exists()
