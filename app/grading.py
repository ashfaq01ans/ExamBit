# Grading rules:
# - single choice and true/false: full marks if the chosen option is the correct one
# - multiple correct: full marks only if the chosen set exactly matches the correct set
# - no negative marking
# - short answer: graded by the teacher. A blank short answer gets 0 automatically.
# attempt.score stays empty until every short answer with text has been graded.


def correct_ids(question):
    return {option.id for option in question.options if option.is_correct}


def compute_totals(attempt):
    """Return (marks earned so far, number of short answers still waiting for the teacher)."""
    questions = {q.id: q for q in attempt.exam.questions}
    earned = 0.0
    pending = 0
    for answer in attempt.answers:
        question = questions.get(answer.question_id)
        if question is None:
            continue
        if answer.marks_awarded is not None:
            earned += answer.marks_awarded
        elif question.qtype == "short" and answer.text_answer and answer.text_answer.strip():
            pending += 1
    return earned, pending


def refresh_score(attempt):
    earned, pending = compute_totals(attempt)
    attempt.score = None if pending else earned


def grade_attempt(attempt):
    """Score the objective answers. Called when an attempt ends."""
    questions = {q.id: q for q in attempt.exam.questions}
    for answer in attempt.answers:
        question = questions.get(answer.question_id)
        if question is None:
            continue
        if question.qtype == "short":
            if not (answer.text_answer and answer.text_answer.strip()):
                answer.marks_awarded = 0.0  # blank: nothing for the teacher to grade
            continue
        chosen = set(answer.selected_option_ids or [])
        right = correct_ids(question)
        answer.marks_awarded = float(question.marks) if chosen and chosen == right else 0.0
    refresh_score(attempt)


def ensure_graded(attempt):
    """Grade attempts that ended before grading existed. Safe to call repeatedly."""
    from app import db

    if attempt.status == "in_progress":
        return
    questions = {q.id: q for q in attempt.exam.questions}
    needs_grading = any(
        a.marks_awarded is None
        and questions.get(a.question_id) is not None
        and questions[a.question_id].qtype != "short"
        for a in attempt.answers
    )
    if needs_grading:
        grade_attempt(attempt)
        db.session.commit()
