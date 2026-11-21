from decimal import Decimal, InvalidOperation, ROUND_CEILING

CENT = Decimal('0.01')
MAX_EXAM_MARKS = Decimal('9999.99')


def question_marks(value):
    try:
        marks = Decimal(str(value))
        if marks.is_finite() and 0 < marks <= MAX_EXAM_MARKS and marks == marks.quantize(CENT):
            return marks.quantize(CENT)
    except (InvalidOperation, ValueError):
        pass
    return Decimal('0.00')


def build_questions(bank_questions, custom_questions):
    questions = [
        {
            'id': q.pk, 'question_text': q.question_text, 'question_type': q.question_type,
            'difficulty': q.difficulty, 'options': q.options if isinstance(q.options, list) else [],
            'marks': str(question_marks(q.marks)),
            'tags': q.tags, 'custom': False,
        }
        for q in bank_questions
    ]
    used_ids = {str(q['id']) for q in questions}
    for index, question in enumerate(custom_questions if isinstance(custom_questions, list) else []):
        if not isinstance(question, dict):
            continue
        key = str(question.get('id') or question.get('question_id') or question.get('key') or f'custom_{index}')
        # Legacy JSON could reuse a bank question ID or another custom ID.
        while key in used_ids:
            key = f'custom_{index}_{key}'
        used_ids.add(key)
        questions.append({
            'id': key, 'question_text': question.get('question_text', question.get('text', '')),
            'question_type': question.get('question_type', question.get('type', 'mcq')),
            'difficulty': str(question.get('difficulty', 'medium')),
            'options': question['options'] if isinstance(question.get('options'), list) else [],
            'marks': str(question_marks(question.get('marks', question.get('max_marks', 1)))),
            'custom': True,
        })
    return questions


def total_question_marks(questions):
    return sum((Decimal(q['marks']) for q in questions), Decimal('0.00'))


def legacy_passing_marks(passing, declared_total, actual_total):
    if 0 < passing <= actual_total:
        return passing
    if not actual_total:
        return Decimal('0.00')
    ratio = min(passing / declared_total, Decimal('1')) if passing > 0 and declared_total > 0 else Decimal('.5')
    return (actual_total * ratio).quantize(CENT, rounding=ROUND_CEILING)


def exam_snapshot(exam, questions, passing_marks):
    return {
        'questions': questions,
        'total_marks': str(total_question_marks(questions)),
        'passing_marks': str(passing_marks),
        'duration_minutes': exam.duration_minutes,
        'window_start': exam.start_datetime.isoformat() if exam.start_datetime else None,
        'window_end': exam.end_datetime.isoformat() if exam.end_datetime else None,
    }
