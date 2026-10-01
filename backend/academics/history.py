from django.apps import apps


def term_has_execution_history(term):
    """Return True once a term has operational evidence that must keep its calendar meaning."""
    checks = [
        ("attendance", "AttendanceSession", {"term_id": term.pk}),
        ("gradebook", "ScoreEntry", {"term_id": term.pk}),
        ("results", "ResultRemark", {"term_id": term.pk}),
        ("timetable", "LessonRecord", {"term_id": term.pk}),
        ("fees", "FeePayment", {"fee_schedule__term_id": term.pk}),
        ("fees", "StudentLedgerEntry", {"term_id": term.pk}),
        ("cbt", "StudentExamSession", {"exam__term_id": term.pk}),
        ("cbt", "AssignmentSubmission", {"assignment__term_id": term.pk}),
    ]
    for app_label, model_name, lookup in checks:
        model = apps.get_model(app_label, model_name)
        if model.objects.filter(**lookup).exists():
            return True
    return False


def session_has_execution_history(session):
    """Session placement or downstream evidence freezes the session identity and dates."""
    SessionEnrollment = apps.get_model("enrollment", "SessionEnrollment")
    PromotionRecord = apps.get_model("promotion", "PromotionRecord")
    if SessionEnrollment.objects.filter(session_id=session.pk).exists():
        return True
    if PromotionRecord.objects.filter(from_session_id=session.pk).exists():
        return True
    return any(term_has_execution_history(term) for term in session.terms.all())
