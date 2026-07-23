from django.utils import timezone
from django.db import IntegrityError, transaction
from decimal import Decimal, InvalidOperation
from .models import QuestionBank, Exam, ExamAttempt, ExamResult


def _decimal_marks(value, default='0'):
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return Decimal(default)


def _answer_matches_options(answer, options):
    if answer is None or answer == '':
        return False

    options = options or []
    answer_text = str(answer).strip()

    try:
        answer_idx = int(answer) if isinstance(answer, str) else answer
    except (TypeError, ValueError):
        answer_idx = None

    if isinstance(answer_idx, int) and 0 <= answer_idx < len(options):
        return bool(options[answer_idx].get('is_correct', False))

    for option in options:
        if (
            option.get('is_correct', False)
            and answer_text.lower() == str(option.get('text', '')).strip().lower()
        ):
            return True

    return False


def _custom_question_key(question, index):
    return str(
        question.get('id')
        or question.get('question_id')
        or question.get('key')
        or f'custom_{index}'
    )


def _custom_question_marks(question):
    return _decimal_marks(question.get('marks', question.get('max_marks', 1)), default='1')


def get_exam_total_possible_marks(exam):
    total = sum((question.marks for question in exam.questions.all()), Decimal('0'))
    total += sum((_custom_question_marks(question) for question in exam.custom_questions or []), Decimal('0'))
    return total


def calculate_exam_attempt_score(attempt):
    exam = attempt.exam
    answers = attempt.answers or {}
    earned = Decimal('0')
    total_possible = Decimal('0')

    for question in exam.questions.all():
        total_possible += question.marks
        answer = answers.get(str(question.id))

        if question.question_type in ['mcq', 'tf'] and _answer_matches_options(answer, question.options):
            earned += question.marks

    for index, question in enumerate(exam.custom_questions or []):
        marks = _custom_question_marks(question)
        total_possible += marks
        answer = answers.get(_custom_question_key(question, index))

        if _answer_matches_options(answer, question.get('options', [])):
            earned += marks

    return earned, total_possible


def start_exam_attempt(exam, user):
    """
    Start a new exam attempt for a user.
    
    Args:
        exam: Exam instance
        user: User instance
    
    Returns:
        ExamAttempt instance
    
    Raises:
        ValueError: If exam is not active or user has exceeded max attempts
    """
    with transaction.atomic():
        locked_exam = Exam.objects.select_for_update().get(pk=exam.pk)

        if not locked_exam.is_active():
            raise ValueError("Exam is not currently available")

        attempts = (
            ExamAttempt.objects
            .select_for_update()
            .filter(exam=locked_exam, user=user)
            .order_by('attempt_number', 'started_at', 'id')
        )

        in_progress = attempts.filter(status='in_progress').first()
        if in_progress:
            if not in_progress.is_expired():
                return in_progress

            in_progress.status = 'abandoned'
            in_progress.save(update_fields=['status'])

        used_attempts = attempts.filter(status__in=['completed', 'abandoned']).count()
        if used_attempts >= locked_exam.max_attempts:
            raise ValueError(f"Maximum attempts ({locked_exam.max_attempts}) exceeded")

        next_attempt_number = (
            attempts.order_by('-attempt_number')
            .values_list('attempt_number', flat=True)
            .first()
            or 0
        ) + 1

        try:
            return ExamAttempt.objects.create(
                exam=locked_exam,
                user=user,
                attempt_number=next_attempt_number
            )
        except IntegrityError:
            in_progress = ExamAttempt.objects.select_for_update().filter(
                exam=locked_exam,
                user=user,
                status='in_progress'
            ).first()
            if in_progress:
                return in_progress
            raise


def submit_exam_attempt(attempt, answers):
    """
    Submit exam attempt with answers.
    
    Args:
        attempt: ExamAttempt instance
        answers: Dictionary of {question_id: answer}
    
    Returns:
        ExamAttempt instance with calculated score
    
    Raises:
        ValueError: If attempt is already completed or expired
    """
    if attempt.status == 'completed':
        raise ValueError("Attempt already completed")
    
    if attempt.is_expired():
        attempt.status = 'abandoned'
        attempt.save()
        raise ValueError("Attempt time has expired")
    
    # Save answers
    attempt.answers = answers
    attempt.completed_at = timezone.now()
    attempt.time_spent_seconds = int((attempt.completed_at - attempt.started_at).total_seconds())
    attempt.status = 'completed'

    earned, total_possible = calculate_exam_attempt_score(attempt)
    attempt.score = earned
    attempt.percentage = (earned / total_possible * 100) if total_possible > 0 else Decimal('0')
    attempt.passed = attempt.score >= attempt.exam.passing_marks
    attempt.auto_graded_at = timezone.now()
    attempt.save(update_fields=[
        'answers',
        'completed_at',
        'time_spent_seconds',
        'status',
        'score',
        'percentage',
        'passed',
        'auto_graded_at',
    ])
    
    # Create detailed result
    create_exam_result(attempt)
    
    return attempt


def create_exam_result(attempt):
    """
    Create detailed result breakdown for an exam attempt.
    
    Args:
        attempt: ExamAttempt instance
    
    Returns:
        ExamResult instance
    """
    exam = attempt.exam
    answers = attempt.answers
    
    question_results = {}
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    
    difficulty_correct = {'easy': 0, 'medium': 0, 'hard': 0}
    
    # Process each question
    for question in exam.questions.all():
        q_id = str(question.id)
        answer = answers.get(q_id)
        
        if answer is None or answer == '':
            unanswered_count += 1
            question_results[q_id] = {
                'correct': False,
                'marks_earned': 0,
                'difficulty': question.difficulty
            }
            continue
        
        is_correct = False
        marks_earned = Decimal('0')
        
        if question.question_type in ['mcq', 'tf']:
            is_correct = _answer_matches_options(answer, question.options)

        if is_correct:
            marks_earned = question.marks
            correct_count += 1
            difficulty_correct[question.difficulty] += 1
        else:
            incorrect_count += 1
        
        question_results[q_id] = {
            'correct': is_correct,
            'marks_earned': float(marks_earned),
            'difficulty': question.difficulty,
            'answer': answer
        }

    for index, question in enumerate(exam.custom_questions or []):
        q_id = _custom_question_key(question, index)
        answer = answers.get(q_id)
        difficulty = question.get('difficulty', 'medium')
        if difficulty not in difficulty_correct:
            difficulty = 'medium'

        if answer is None or answer == '':
            unanswered_count += 1
            question_results[q_id] = {
                'correct': False,
                'marks_earned': 0,
                'difficulty': difficulty,
            }
            continue

        is_correct = _answer_matches_options(answer, question.get('options', []))
        marks_earned = _custom_question_marks(question) if is_correct else Decimal('0')
        if is_correct:
            correct_count += 1
            difficulty_correct[difficulty] += 1
        else:
            incorrect_count += 1

        question_results[q_id] = {
            'correct': is_correct,
            'marks_earned': float(marks_earned),
            'difficulty': difficulty,
            'answer': answer,
            'custom': True,
        }
    
    # Create or update result
    result, created = ExamResult.objects.update_or_create(
        attempt=attempt,
        defaults={
            'question_results': question_results,
            'correct_count': correct_count,
            'incorrect_count': incorrect_count,
            'unanswered_count': unanswered_count,
            'easy_correct': difficulty_correct['easy'],
            'medium_correct': difficulty_correct['medium'],
            'hard_correct': difficulty_correct['hard']
        }
    )
    
    return result


def calculate_exam_score(attempt):
    """
    Calculate score for an exam attempt.
    
    Args:
        attempt: ExamAttempt instance
    
    Returns:
        Decimal: Total score earned
    """
    total_score, _ = calculate_exam_attempt_score(attempt)
    return total_score


def get_exam_analytics(exam):
    """
    Get analytics for an exam.
    
    Args:
        exam: Exam instance
    
    Returns:
        Dictionary with analytics data
    """
    attempts = ExamAttempt.objects.filter(exam=exam, status='completed')
    
    total_attempts = attempts.count()
    if total_attempts == 0:
        return {
            'total_attempts': 0,
            'average_score': 0,
            'pass_rate': 0,
            'question_analytics': []
        }
    
    # Calculate averages
    scores = [float(a.score) for a in attempts if a.score]
    average_score = sum(scores) / len(scores) if scores else 0
    
    passed_count = attempts.filter(passed=True).count()
    pass_rate = (passed_count / total_attempts) * 100
    
    # Question-wise analytics
    question_analytics = []
    for question in exam.questions.all():
        q_id = str(question.id)
        
        total_answered = 0
        correct_answered = 0
        
        for attempt in attempts:
            if q_id in attempt.answers:
                total_answered += 1
                
                # Check if correct
                correct_options = [opt for opt in question.options if opt.get('is_correct')]
                if correct_options:
                    correct_answer = correct_options[0].get('text')
                    if str(attempt.answers[q_id]).strip().lower() == str(correct_answer).strip().lower():
                        correct_answered += 1
        
        correct_percentage = (correct_answered / total_answered * 100) if total_answered > 0 else 0
        
        question_analytics.append({
            'question_id': question.id,
            'question_text': question.question_text[:100],
            'difficulty': question.difficulty,
            'correct_percentage': round(correct_percentage, 2),
            'total_attempts': total_answered
        })
    
    return {
        'total_attempts': total_attempts,
        'average_score': round(average_score, 2),
        'pass_rate': round(pass_rate, 2),
        'question_analytics': question_analytics
    }
