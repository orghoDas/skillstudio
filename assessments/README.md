# 📝 Assessments App

Comprehensive assessment system for quizzes, assignments, and grading in SkillStudio LMS.

## 🎯 Features

### Quizzes
- **Auto-graded MCQ & True/False questions**
- **Timed quizzes** with automatic submission
- **Real-time attempt tracking**
- **Score calculation** with detailed feedback
- **Multiple attempts** support (configurable)
- **Question difficulty levels** (easy, medium, hard)

### Assignments
- **Text submissions** with file upload support
- **Manual grading** by instructors
- **Rubric-based grading** with criteria
- **Feedback mechanism** for students
- **Resubmission support** (configurable)
- **Grade export** capabilities

### Grading
- **Automatic grading** for quizzes (MCQ/TF)
- **Manual grading** for assignments
- **Rubric-based evaluation** with multiple criteria
- **Bulk grading** for instructors
- **Grade analytics** and reports
- **Feedback templates**

## 📊 Models

### Quiz
```python
quiz = Quiz.objects.create(
    lesson=lesson,
    title="Python Basics Quiz",
    description="Test your Python knowledge",
    total_marks=100,
    passing_marks=60,
    time_limit_minutes=30,  # Optional
    max_attempts=3,  # Optional
    randomize_questions=True,
    show_answers_after_submission=True
)
```

### QuizQuestion
```python
question = QuizQuestion.objects.create(
    quiz=quiz,
    question_text="What is the output of print(2 ** 3)?",
    question_type='mcq',  # or 'tf' for True/False
    difficulty='medium',
    marks=5,
    explanation="2 ** 3 means 2 raised to power 3, which equals 8"
)
```

### QuestionOption
```python
option = QuestionOption.objects.create(
    question=question,
    option_text="8",
    is_correct=True
)
```

### QuizAttempt
```python
attempt = QuizAttempt.objects.create(
    quiz=quiz,
    user=student,
    answers={
        "question_id": "option_id",  # For MCQ
        "question_id": "True"  # For True/False
    }
)
```

### Assignment
```python
assignment = Assignment.objects.create(
    lesson=lesson,
    title="Python Project",
    instructions="Build a simple calculator",
    max_score=100,
    due_date=timezone.now() + timedelta(days=7),
    allow_late_submission=True,
    max_file_size_mb=10
)
```

### Submission
```python
submission = Submission.objects.create(
    assignment=assignment,
    user=student,
    text="Here is my solution...",
    file="path/to/file.zip",
    submitted_at=timezone.now()
)
```

### Rubric
```python
rubric = Rubric.objects.create(
    assignment=assignment,
    total_marks=100,
    criteria=[
        {
            "key": "code_quality",
            "label": "Code Quality",
            "description": "Clean, readable code",
            "max": 30
        },
        {
            "key": "functionality",
            "label": "Functionality",
            "description": "All features working",
            "max": 50
        },
        {
            "key": "documentation",
            "label": "Documentation",
            "description": "Good comments and README",
            "max": 20
        }
    ]
)
```

## 🔌 API Endpoints

### Quiz Endpoints

#### Get Quiz by Lesson
```http
GET /api/assessments/quiz/lesson/{lesson_id}/
```
**Response:**
```json
{
    "id": 1,
    "title": "Python Basics Quiz",
    "description": "Test your Python knowledge",
    "total_marks": 100,
    "passing_marks": 60,
    "time_limit_minutes": 30,
    "questions": [
        {
            "id": 1,
            "question_text": "What is 2 + 2?",
            "question_type": "mcq",
            "difficulty": "easy",
            "marks": 5,
            "options": [
                {"id": 1, "option_text": "3", "is_correct": false},
                {"id": 2, "option_text": "4", "is_correct": true}
            ]
        }
    ]
}
```

#### Start Quiz Attempt
```http
POST /api/assessments/quiz/{quiz_id}/start/
```
**Response:**
```json
{
    "attempt_id": 123,
    "started_at": "2024-01-15T10:00:00Z",
    "time_remaining_seconds": 1800,
    "message": "Quiz attempt started"
}
```

#### Submit Quiz
```http
POST /api/assessments/quiz/{quiz_id}/submit/
```
**Request Body:**
```json
{
    "attempt_id": 123,
    "answers": {
        "1": "2",  // question_id: option_id
        "2": "True"
    }
}
```
**Response:**
```json
{
    "score": 85,
    "total_marks": 100,
    "percentage": 85,
    "passed": true,
    "correct_answers": 17,
    "total_questions": 20,
    "time_taken_seconds": 1200,
    "feedback": "Great job!"
}
```

#### Get Quiz Attempts History
```http
GET /api/assessments/quiz/{quiz_id}/attempts/
```
**Response:**
```json
{
    "attempts": [
        {
            "id": 123,
            "started_at": "2024-01-15T10:00:00Z",
            "completed_at": "2024-01-15T10:20:00Z",
            "score": 85,
            "percentage": 85,
            "passed": true
        }
    ]
}
```

### Assignment Endpoints

#### Get Assignment by Lesson
```http
GET /api/assessments/assignment/lesson/{lesson_id}/
```
**Response:**
```json
{
    "id": 1,
    "title": "Python Project",
    "instructions": "Build a calculator",
    "max_score": 100,
    "due_date": "2024-01-22T23:59:59Z",
    "has_rubric": true,
    "my_submission": {
        "id": 45,
        "submitted_at": "2024-01-20T15:30:00Z",
        "grade": 92,
        "feedback": "Excellent work!"
    }
}
```

#### Submit Assignment
```http
POST /api/assessments/assignment/{assignment_id}/submit/
Content-Type: multipart/form-data
```
**Request Body:**
```
text: "My solution..."
file: (binary)
```
**Response:**
```json
{
    "id": 45,
    "submitted_at": "2024-01-20T15:30:00Z",
    "message": "Assignment submitted successfully"
}
```

### Grading Endpoints (Instructors Only)

#### Get Pending Submissions
```http
GET /api/assessments/grading/assignment/{assignment_id}/pending/
```
**Response:**
```json
{
    "submissions": [
        {
            "id": 45,
            "student": {
                "id": 10,
                "name": "John Doe",
                "email": "john@example.com"
            },
            "submitted_at": "2024-01-20T15:30:00Z",
            "text": "My solution...",
            "file_url": "https://..."
        }
    ]
}
```

#### Grade Submission
```http
POST /api/assessments/grading/submission/{submission_id}/grade/
```
**Request Body:**
```json
{
    "grade": 92,
    "feedback": "Excellent work! Your code is clean and well-documented."
}
```

#### Grade with Rubric
```http
POST /api/assessments/grading/submission/{submission_id}/grade-rubric/
```
**Request Body:**
```json
{
    "rubric_scores": {
        "code_quality": 28,
        "functionality": 48,
        "documentation": 19
    },
    "feedback": "Great project overall!"
}
```

#### Bulk Grade Submissions
```http
POST /api/assessments/grading/bulk-grade/
```
**Request Body:**
```json
{
    "grades": [
        {
            "submission_id": 45,
            "grade": 92,
            "feedback": "Excellent!"
        },
        {
            "submission_id": 46,
            "grade": 78,
            "feedback": "Good work, but needs improvement."
        }
    ]
}
```

### Analytics Endpoints (Instructors Only)

#### Quiz Analytics
```http
GET /api/assessments/analytics/quiz/{quiz_id}/
```
**Response:**
```json
{
    "total_attempts": 45,
    "average_score": 82.5,
    "pass_rate": 88.9,
    "question_analytics": [
        {
            "question_id": 1,
            "question_text": "What is 2 + 2?",
            "correct_percentage": 95.5,
            "average_time_seconds": 12
        }
    ]
}
```

#### Assignment Analytics
```http
GET /api/assessments/analytics/assignment/{assignment_id}/
```
**Response:**
```json
{
    "total_submissions": 42,
    "graded_count": 38,
    "pending_count": 4,
    "average_grade": 85.3,
    "grade_distribution": {
        "A": 15,
        "B": 18,
        "C": 5,
        "D": 0,
        "F": 0
    }
}
```

## 🔧 Services

### Quiz Services

```python
from assessments.services import start_quiz_attempt, submit_quiz_attempt

# Start a quiz attempt
attempt = start_quiz_attempt(quiz, user)

# Submit quiz
result = submit_quiz_attempt(
    attempt,
    answers={
        "1": "2",  # question_id: option_id
        "2": "True"
    }
)
```

### Scoring Services

```python
from assessments.services_scoring import calculate_quiz_score

score = calculate_quiz_score(attempt)
```

### Grading Services

```python
from assessments.grading_services import grade_submission, grade_submission_with_rubric

# Simple grading
graded = grade_submission(submission, grade=92, feedback="Excellent!")

# Rubric-based grading
graded = grade_submission_with_rubric(
    submission,
    rubric_scores={
        "code_quality": 28,
        "functionality": 48,
        "documentation": 19
    },
    feedback="Great work!"
)
```

## 🧪 Testing

Run tests:
```bash
python manage.py test assessments
```

Run specific test:
```bash
python manage.py test assessments.tests.QuizModelTest
```

## 📈 Usage Examples

### Creating a Quiz

```python
from courses.models import Lesson
from assessments.models import Quiz, QuizQuestion, QuestionOption

# Get lesson
lesson = Lesson.objects.get(id=1)

# Create quiz
quiz = Quiz.objects.create(
    lesson=lesson,
    title="Python Basics",
    total_marks=100,
    time_limit_minutes=30
)

# Add question
question = QuizQuestion.objects.create(
    quiz=quiz,
    question_text="What is the capital of France?",
    question_type='mcq',
    marks=5
)

# Add options
QuestionOption.objects.create(question=question, option_text="London", is_correct=False)
QuestionOption.objects.create(question=question, option_text="Paris", is_correct=True)
QuestionOption.objects.create(question=question, option_text="Berlin", is_correct=False)
```

### Taking a Quiz

```python
from assessments.services import start_quiz_attempt, submit_quiz_attempt

# Start attempt
attempt = start_quiz_attempt(quiz, request.user)

# Submit answers
result = submit_quiz_attempt(attempt, {
    str(question.id): str(correct_option.id)
})

print(f"Score: {result['score']}/{result['total_marks']}")
```

### Creating an Assignment

```python
from assessments.models import Assignment, Rubric

# Create assignment
assignment = Assignment.objects.create(
    lesson=lesson,
    title="Build a Calculator",
    instructions="Create a Python calculator with basic operations",
    max_score=100
)

# Create rubric
Rubric.objects.create(
    assignment=assignment,
    total_marks=100,
    criteria=[
        {"key": "functionality", "label": "Functionality", "max": 50},
        {"key": "code_quality", "label": "Code Quality", "max": 30},
        {"key": "documentation", "label": "Documentation", "max": 20}
    ]
)
```

### Grading an Assignment

```python
from assessments.grading_services import grade_submission_with_rubric

submission = Submission.objects.get(id=45)

graded = grade_submission_with_rubric(
    submission,
    rubric_scores={
        "functionality": 48,
        "code_quality": 28,
        "documentation": 18
    },
    feedback="Great work! Your calculator works perfectly."
)
```

## 🔐 Permissions

- **Students**: Can view quizzes, take quizzes, submit assignments, view their own grades
- **Instructors**: Can create quizzes/assignments, grade submissions, view analytics
- **Admins**: Full access to all features

## 🚀 Next Steps

1. **Add more question types** (fill-in-the-blank, essay questions)
2. **Implement peer review** for assignments
3. **Add quiz question pools** for randomization
4. **Create grade export** to Excel/CSV
5. **Add plagiarism detection** for assignments
6. **Implement automated feedback** for common mistakes

## 📚 Related Apps

- **courses**: Provides lessons for assessments
- **enrollments**: Tracks student progress
- **certificates**: Issues certificates based on assessment completion
- **analytics**: Provides detailed analytics

## 🤝 Contributing

When contributing to this app:
1. Write comprehensive tests for new features
2. Update API documentation
3. Add usage examples
4. Follow Django best practices
5. Use meaningful commit messages

## 📝 License

Part of the SkillStudio LMS project.
