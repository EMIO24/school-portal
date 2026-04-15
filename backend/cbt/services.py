"""
backend/cbt/services.py

CBT business logic extracted from views for reuse and testability.
"""

from decimal import Decimal

from django.utils import timezone

from .models import StudentAnswer, StudentExamSession


def auto_mark(session: StudentExamSession, final_status: str = 'submitted') -> None:
    """
    Mark all answers in a session correct/incorrect and compute a percentage score.

    Steps:
      1. Fetch all questions for this session.
      2. For each question, reverse the option shuffle map (if any) to recover the
         original option id the student chose.
      3. Compare to Question.correct_answer.
         - MCQ / True-False: exact string match after reversing shuffle.
         - Fill-blank: case-insensitive, stripped text compare.
      4. Persist is_correct on each StudentAnswer.
      5. Write score (percentage, 2 d.p.) and status to the session.

    This function is idempotent — calling it twice on the same session is safe.
    """
    from .models import Question  # local import avoids circular

    q_ids     = session.question_order
    questions = {q.id: q for q in Question.objects.filter(id__in=q_ids)}
    answers   = {a.question_id: a for a in session.answers.all()}

    correct = 0
    total   = len(q_ids)

    for q_id in q_ids:
        q   = questions.get(q_id)
        ans = answers.get(q_id)
        if not q or not ans:
            continue

        # Reverse shuffle map: {shuffled_id: original_id}
        omap = session.option_maps.get(str(q_id), {})
        reverse_map = {v: k for k, v in omap.items()}
        original_selected = reverse_map.get(ans.selected_option, ans.selected_option)

        if q.question_type == 'fill_blank':
            is_correct = (
                original_selected.strip().lower() == q.correct_answer.strip().lower()
            )
        else:
            is_correct = original_selected == q.correct_answer

        ans.is_correct = is_correct
        ans.save(update_fields=['is_correct'])
        if is_correct:
            correct += 1

    session.score        = round(Decimal(correct) / Decimal(total) * 100, 2) if total else Decimal('0')
    session.status       = final_status
    session.submitted_at = timezone.now()
    session.save(update_fields=['score', 'status', 'submitted_at'])
