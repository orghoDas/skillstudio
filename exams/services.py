from datetime import timezone as dt_timezone
from random import Random
from secrets import token_hex

from django.utils import timezone
from django.db import transaction
from django.utils.dateparse import parse_datetime
from decimal import Decimal
from .grading import MAX_EXAM_MARKS, build_questions, exam_snapshot, legacy_passing_marks, total_question_marks
from .models import Exam, ExamAttempt, ExamResult


class ExamUnavailable(ValueError):
    """An exam action refused for a reason the student should see (EXM-01)."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def _fmt(dt):
    return dt.astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def exam_availability(exam, now=None):
    """'open', 'not_open_yet', 'closed' or 'not_published'."""
    now = now or timezone.now()
    if exam.status != 'published':
        return 'not_published'
    if exam.start_datetime and now < exam.start_datetime:
        return 'not_open_yet'
    if exam.end_datetime and now > exam.end_datetime:
        return 'closed'
    return 'open'


def ensure_exam_open(exam):
    """Raise ExamUnavailable unless students may start the exam right now."""
    availability = exam_availability(exam)
    if availability == 'not_open_yet':
        raise ExamUnavailable(f"This exam opens at {_fmt(exam.start_datetime)}.", 'not_open_yet')
    if availability == 'closed':
        raise ExamUnavailable(f"This exam closed at {_fmt(exam.end_datetime)}.", 'closed')
    if availability == 'not_published':
        raise ExamUnavailable("This exam isn't available.", 'not_published')


def attempt_started_within_window(attempt):
    """An attempt counts only if it was started inside the exam's window.

    (A student who starts near the end may still finish within the attempt's
    own duration; the window limits when attempts can *start*.)
    """
    if attempt.snapshot is None:
        start, end = attempt.exam.start_datetime, attempt.exam.end_datetime
    else:
        start = parse_datetime(attempt.snapshot['window_start']) if attempt.snapshot['window_start'] else None
        end = parse_datetime(attempt.snapshot['window_end']) if attempt.snapshot['window_end'] else None
    return (start is None or attempt.started_at >= start) and (end is None or attempt.started_at <= end)


def graded_course_exam_attempts(user, course):
    attempts = ExamAttempt.objects.filter(
        user=user, exam__course=course, exam__status='published',
        status='completed', score__isnull=False,
    ).select_related('exam').order_by('pk')
    return (attempt for attempt in attempts if attempt_started_within_window(attempt))


def course_exam_requirements_met(user, course):
    # An exam with a closing date is optional for course completion.
    required_ids = set(course.exams.filter(
        status='published', end_datetime__isnull=True,
    ).values_list('pk', flat=True))
    if not required_ids:
        return True
    passed_ids = {attempt.exam_id for attempt in graded_course_exam_attempts(user, course) if attempt.passed}
    return required_ids <= passed_ids


def current_exam_questions(exam):
    return build_questions(exam.questions.all(), exam.custom_questions)


def ensure_question_bank_matches_course(exam):
    if exam.questions.exclude(course_id=exam.course_id).exists():
        raise ExamUnavailable("Select questions from this exam’s course.", 'invalid_question_course')


def validated_exam_total(questions, passing_marks):
    if not questions:
        raise ExamUnavailable("Cannot publish or start an exam with no questions.", 'no_questions')
    total = total_question_marks(questions)
    if total > MAX_EXAM_MARKS or any(Decimal(q['marks']) <= 0 for q in questions):
        raise ExamUnavailable("Question marks must be positive and the total must fit within 9999.99.", 'invalid_marks')
    for question in questions:
        options = question['options']
        if len(options) < 2 or any(not isinstance(option, dict) for option in options) or sum(
            bool(option.get('is_correct')) for option in options
        ) != 1:
            raise ExamUnavailable("Every question must have at least two options and one correct answer.", 'invalid_options')
    if not 0 < passing_marks <= total:
        raise ExamUnavailable("Passing marks must be greater than zero and at most the question total.", 'invalid_passing_marks')
    return total


def _ensure_snapshot(attempt):
    if attempt.snapshot is None:
        exam = attempt.exam
        questions = current_exam_questions(exam)
        passing = legacy_passing_marks(exam.passing_marks, exam.total_marks, total_question_marks(questions))
        attempt.snapshot = exam_snapshot(exam, questions, passing)
        attempt.save(update_fields=['snapshot'])


def _ensure_attempt_can_be_graded(attempt):
    if attempt.exam.status != 'published':
        raise ExamUnavailable("This exam is no longer available.", 'not_published')
    if not attempt_started_within_window(attempt):
        raise ExamUnavailable("This attempt wasn't started within the exam window.", 'outside_window')


def start_exam_attempt(exam, user):
    refusal = None
    with transaction.atomic():
        exam = Exam.objects.select_for_update().get(pk=exam.pk)
        ensure_question_bank_matches_course(exam)
        attempts = ExamAttempt.objects.filter(exam=exam, user=user)
        active = attempts.select_for_update().filter(status='in_progress').first()
        if active:
            active.exam = exam
            _ensure_attempt_can_be_graded(active)
            _ensure_snapshot(active)
            if not active.is_expired():
                return active
            _grade_attempt(active, completed_at=active.deadline)

        # Let any overdue grading commit even if the next attempt is refused.
        try:
            ensure_exam_open(exam)
            if attempts.filter(retry_granted=False).count() >= exam.max_attempts:
                raise ExamUnavailable(
                    f"You have used all {exam.max_attempts} attempt(s) for this exam.", 'max_attempts'
                )
            questions = current_exam_questions(exam)
            validated_exam_total(questions, exam.passing_marks)
        except ExamUnavailable as exc:
            refusal = exc
        else:
            previous = attempts.order_by('-attempt_number').values_list('attempt_number', flat=True).first()
            seed = token_hex(16) if exam.randomize_questions else None
            if seed is not None:
                Random(seed).shuffle(questions)
            snapshot = exam_snapshot(exam, questions, exam.passing_marks)
            if seed is not None:
                snapshot['question_order_seed'] = seed
            return ExamAttempt.objects.create(
                exam=exam, user=user, attempt_number=(previous or 0) + 1,
                snapshot=snapshot,
            )

    raise refusal


def selected_option_index(answer, options):
    try:
        answer_idx = int(answer) if isinstance(answer, str) else answer
    except ValueError:
        return None
    return answer_idx if type(answer_idx) is int and 0 <= answer_idx < len(options) else None


def _answer_matches_options(answer, options):
    if answer is None or answer == '':
        return False
    options = options or []
    answer_idx = selected_option_index(answer, options)
    if answer_idx is not None:
        option = options[answer_idx]
        return isinstance(option, dict) and bool(option.get('is_correct'))
    answer_text = str(answer).strip().lower()
    return any(
        isinstance(option, dict) and option.get('is_correct')
        and answer_text == str(option.get('text', '')).strip().lower()
        for option in options
    )


def _merge_answers(attempt, answers):
    valid_ids = {str(q['id']) for q in attempt.snapshot['questions']}
    if set(answers) - valid_ids:
        raise ExamUnavailable("Answers must reference questions in this attempt.", 'invalid_question')
    attempt.answers = {**(attempt.answers or {}), **answers}


@transaction.atomic
def record_exam_answers(attempt, answers=None, *, submit=False):
    """Save answer changes, optionally submit, or finalize an overdue attempt."""
    exam = Exam.objects.select_for_update().get(pk=attempt.exam_id)
    attempt = ExamAttempt.objects.select_for_update().get(pk=attempt.pk)
    attempt.exam = exam
    _ensure_attempt_can_be_graded(attempt)
    if attempt.status == 'completed':
        return attempt
    if attempt.status != 'in_progress':
        raise ExamUnavailable("This attempt is no longer in progress.", 'attempt_closed')
    _ensure_snapshot(attempt)

    now = timezone.now()
    if attempt.is_expired(now):
        return _grade_attempt(attempt, completed_at=attempt.deadline)
    if answers is not None:
        _merge_answers(attempt, answers)
    if submit:
        return _grade_attempt(attempt, completed_at=now)
    if answers is not None:
        attempt.save(update_fields=['answers'])
    return attempt


def submit_exam_attempt(attempt, answers):
    return record_exam_answers(attempt, answers, submit=True)


def _grade_attempt(attempt, *, completed_at):
    breakdown = {}
    counts = {'correct_count': 0, 'incorrect_count': 0, 'unanswered_count': 0}
    difficulty_counts = {'easy': 0, 'medium': 0, 'hard': 0}
    earned = Decimal('0.00')
    for question in attempt.snapshot['questions']:
        key = str(question['id'])
        answer = (attempt.answers or {}).get(key)
        answered = answer is not None and answer != ''
        correct = _answer_matches_options(answer, question['options'])
        marks = Decimal(question['marks']) if correct else Decimal('0.00')
        difficulty = question['difficulty']
        if difficulty not in difficulty_counts:
            difficulty = 'medium'
        if correct:
            counts['correct_count'] += 1
            difficulty_counts[difficulty] += 1
        elif answered:
            counts['incorrect_count'] += 1
        else:
            counts['unanswered_count'] += 1
        earned += marks
        breakdown[key] = {
            'correct': correct, 'marks_earned': float(marks), 'difficulty': difficulty,
            'answer': answer, 'custom': question['custom'],
        }

    total = attempt.grading_total_marks
    attempt.score = earned
    attempt.percentage = (earned * 100 / total).quantize(Decimal('0.01')) if total else Decimal('0.00')
    attempt.passed = bool(total and earned >= Decimal(attempt.snapshot['passing_marks']))
    attempt.status = 'completed'
    attempt.completed_at = completed_at
    attempt.auto_graded_at = timezone.now()
    attempt.time_spent_seconds = max(0, int((completed_at - attempt.started_at).total_seconds()))
    attempt.save(update_fields=[
        'answers', 'score', 'percentage', 'passed', 'status',
        'completed_at', 'auto_graded_at', 'time_spent_seconds',
    ])
    ExamResult.objects.update_or_create(
        attempt=attempt,
        defaults={
            'question_results': breakdown,
            **counts,
            **{f'{difficulty}_correct': count for difficulty, count in difficulty_counts.items()},
        },
    )
    if attempt.passed:
        from enrollments.models import Enrollment
        from enrollments.services import evaluate_and_complete_enrollment

        enrollment_id = Enrollment.objects.filter(
            user_id=attempt.user_id, course_id=attempt.exam.course_id,
        ).values_list('pk', flat=True).first()
        if enrollment_id is not None:
            evaluate_and_complete_enrollment(enrollment_id)
    return attempt


def get_exam_analytics(exam):
    """Summarize completed grades, preferring the questions captured at grading."""
    attempts = list(ExamAttempt.objects.filter(exam=exam, status='completed').select_related('result'))
    if not attempts:
        return {
            'total_attempts': 0,
            'average_score': 0,
            'pass_rate': 0,
            'question_analytics': []
        }
    
    scores = [attempt.score for attempt in attempts if attempt.score is not None]
    average_score = sum(scores) / len(scores) if scores else 0
    pass_rate = sum(attempt.passed is True for attempt in attempts) / len(attempts) * 100
    questions = {}
    current_questions = build_questions(exam.questions.filter(course_id=exam.course_id), exam.custom_questions)
    for attempt in attempts:
        snapshot_questions = attempt.snapshot['questions'] if attempt.snapshot is not None else current_questions
        breakdown = attempt.result.question_results if hasattr(attempt, 'result') else {}
        for question in snapshot_questions:
            key = str(question['id'])
            stats = questions.setdefault(key, {
                'question_id': question['id'],
                'question_text': question['question_text'][:100],
                'difficulty': question['difficulty'],
                'total_attempts': 0,
                'correct': 0,
            })
            answer = (attempt.answers or {}).get(key)
            if answer is None or answer == '':
                continue
            graded = breakdown.get(key, {}).get('correct')
            if not isinstance(graded, bool):
                graded = _answer_matches_options(answer, question['options'])
            stats['total_attempts'] += 1
            stats['correct'] += graded

    for stats in questions.values():
        answered = stats['total_attempts']
        correct = stats.pop('correct')
        stats['correct_percentage'] = round(correct * 100 / answered, 2) if answered else 0

    return {
        'total_attempts': len(attempts),
        'average_score': round(float(average_score), 2),
        'pass_rate': round(pass_rate, 2),
        'question_analytics': list(questions.values()),
    }
