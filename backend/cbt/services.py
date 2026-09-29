"""
backend/cbt/services.py

CBT business logic extracted from views for reuse and testability.
"""

from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

def session_questions(session):
    from .models import Question
    if session.question_snapshot:
        return {row["id"]: SimpleNamespace(**row) for row in session.question_snapshot}
    return {q.id:q for q in Question.objects.filter(id__in=session.question_order)}


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
    questions = session_questions(session)
    answers   = {a.question_id: a for a in session.answers.all()}

    correct = Decimal('0')
    total = sum((Decimal(str(getattr(questions[q_id], 'marks', 1))) for q_id in q_ids if q_id in questions), Decimal('0'))

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
            is_correct = bool(original_selected) and (
                original_selected.strip().lower() == q.correct_answer.strip().lower()
            )
        else:
            is_correct = original_selected == q.correct_answer

        ans.is_correct = is_correct
        ans.save(update_fields=['is_correct'])
        if is_correct:
            correct += Decimal(str(getattr(q, 'marks', 1)))

    session.raw_score = correct
    session.raw_maximum = total
    session.score = (correct / total * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if total else Decimal('0')
    session.status       = final_status
    session.submitted_at = timezone.now()
    session.save(update_fields=['raw_score', 'raw_maximum', 'score', 'status', 'submitted_at'])
