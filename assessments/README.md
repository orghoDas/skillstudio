# Assessments App

The assessments app now provides lesson-level MCQ quizzes only.

## Features

- Instructor-managed quizzes attached to course lessons
- Auto-graded multiple-choice questions
- Timed quiz attempts
- Single active/completed attempt per user per quiz
- Quiz score, pass/fail state, and question-option analytics

## Models

### Quiz

```python
quiz = Quiz.objects.create(
    lesson=lesson,
    title="Python Basics Quiz",
    total_marks=100,
    passing_percentage=60,
    time_limit_minutes=30,
)
```

### QuizQuestion

```python
question = QuizQuestion.objects.create(
    quiz=quiz,
    question_text="What is the output of print(2 ** 3)?",
    difficulty="medium",
    marks=5,
)
```

### QuestionOption

```python
QuestionOption.objects.create(
    question=question,
    option_text="8",
    is_correct=True,
)
QuestionOption.objects.create(
    question=question,
    option_text="6",
    is_correct=False,
)
```

### QuizAttempt

```python
attempt = QuizAttempt.objects.create(
    quiz=quiz,
    user=student,
    answers={"question_id": "option_id"},
)
```

## API Surface

- `GET /api/assessments/quiz/lesson/{lesson_id}/`
- `POST /api/assessments/quiz/lesson/{lesson_id}/start/`
- `POST /api/assessments/quiz/attempt/{attempt_id}/submit/`
- `GET /api/assessments/manage/quiz/lesson/{lesson_id}/`
- `POST /api/assessments/manage/quiz/lesson/{lesson_id}/`
- `GET /api/assessments/analytics/course/{course_id}/overview/`
- `GET /api/assessments/analytics/quiz/{quiz_id}/questions/`

Question payloads may omit `type`; when provided it must be `mcq`.
