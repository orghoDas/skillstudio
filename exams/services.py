from django.utils import timezone
from decimal import Decimal
from .models import QuestionBank, Exam, ExamAttempt, ExamResult


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
    # Check if exam is active
    if not exam.is_active():
        raise ValueError("Exam is not currently available")
    
    # Check max attempts
    existing_attempts = ExamAttempt.objects.filter(
        exam=exam,
        user=user,
        status='completed'
    ).count()
    
    if existing_attempts >= exam.max_attempts:
        raise ValueError(f"Maximum attempts ({exam.max_attempts}) exceeded")
    
    # Check for in-progress attempts
    in_progress = ExamAttempt.objects.filter(
        exam=exam,
        user=user,
        status='in_progress'
    ).first()
    
    if in_progress:
        # Check if expired
        if in_progress.is_expired():
            in_progress.status = 'abandoned'
            in_progress.save()
        else:
            return in_progress
    
    # Create new attempt
    attempt = ExamAttempt.objects.create(
        exam=exam,
        user=user
    )
    
    return attempt


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
    
    # Calculate score
    attempt.calculate_score()
    
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
        
        if not answer:
            unanswered_count += 1
            question_results[q_id] = {
                'correct': False,
                'marks_earned': 0,
                'difficulty': question.difficulty
            }
            continue
        
        # Check if correct (for MCQ and TF)
        is_correct = False
        marks_earned = 0
        
        if question.question_type in ['mcq', 'tf']:
            correct_options = [opt for opt in question.options if opt.get('is_correct')]
            if correct_options:
                correct_answer = correct_options[0].get('text')
                is_correct = str(answer).strip().lower() == str(correct_answer).strip().lower()
                
                if is_correct:
                    marks_earned = float(question.marks)
                    correct_count += 1
                    difficulty_correct[question.difficulty] += 1
                else:
                    incorrect_count += 1
        
        question_results[q_id] = {
            'correct': is_correct,
            'marks_earned': marks_earned,
            'difficulty': question.difficulty,
            'answer': answer
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
    total_score = Decimal('0')
    
    for question in attempt.exam.questions.filter(question_type__in=['mcq', 'tf']):
        q_id = str(question.id)
        answer = attempt.answers.get(q_id)
        
        if answer:
            correct_options = [opt for opt in question.options if opt.get('is_correct')]
            if correct_options:
                correct_answer = correct_options[0].get('text')
                if str(answer).strip().lower() == str(correct_answer).strip().lower():
                    total_score += question.marks
    
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


def grade_manual_questions(attempt, manual_grades, graded_by):
    """
    Manually grade essay/short answer questions.
    
    Args:
        attempt: ExamAttempt instance
        manual_grades: Dictionary of {question_id: marks_awarded}
        graded_by: User who is grading
    
    Returns:
        Updated ExamAttempt instance
    """
    # Add manual grades to auto-calculated score
    additional_marks = sum(Decimal(str(marks)) for marks in manual_grades.values())
    
    attempt.score = (attempt.score or Decimal('0')) + additional_marks
    attempt.percentage = (attempt.score / attempt.exam.total_marks * 100) if attempt.exam.total_marks > 0 else Decimal('0')
    attempt.passed = attempt.score >= attempt.exam.passing_marks
    attempt.manually_graded_at = timezone.now()
    attempt.graded_by = graded_by
    attempt.save()
    
    # Update result with manual grades
    if hasattr(attempt, 'result'):
        result = attempt.result
        question_results = result.question_results
        
        for q_id, marks in manual_grades.items():
            if q_id in question_results:
                question_results[q_id]['marks_earned'] = float(marks)
                question_results[q_id]['manually_graded'] = True
        
        result.question_results = question_results
        result.save()
    
    return attempt
