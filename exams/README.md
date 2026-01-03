# 🎓 Exams App

Comprehensive final examination system with question banks and detailed analytics for SkillStudio LMS.

## 🎯 Features

### Question Bank
- **Reusable question library** organized by course
- **Multiple question types**: MCQ, True/False, Short Answer, Essay
- **Difficulty levels**: Easy, Medium, Hard
- **Tagging system** for categorization
- **Question versioning** and history
- **Bulk import/export** capabilities

### Exams
- **Draft/Published/Archived** status workflow
- **Scheduled exams** with start and end dates
- **Timed exams** with auto-submission
- **Question randomization** for fairness
- **Multiple attempts** (configurable)
- **Instant or delayed results**
- **Mix of auto and manual grading**

### Results & Analytics
- **Detailed result breakdown** by question
- **Difficulty-wise performance** analysis
- **Question-level statistics** for instructors
- **Pass/fail tracking**
- **Time spent analysis**
- **Performance trends**

## 📊 Models

### QuestionBank
```python
question = QuestionBank.objects.create(
    course=course,
    question_text="Explain the concept of polymorphism in OOP",
    question_type='essay',  # mcq, tf, short, essay
    difficulty='hard',
    marks=20,
    correct_answer="Model answer for instructors...",
    explanation="Key points to cover...",
    tags=["oop", "advanced", "theory"],
    created_by=instructor
)
```

### Exam
```python
exam = Exam.objects.create(
    course=course,
    title="Python Programming Final Exam",
    description="Comprehensive final examination",
    total_marks=100,
    passing_marks=60,
    duration_minutes=120,
    start_datetime=timezone.now(),
    end_datetime=timezone.now() + timedelta(days=7),
    max_attempts=2,
    randomize_questions=True,
    show_results_immediately=False,
    show_correct_answers=False,
    status='published',
    created_by=instructor
)

# Add questions from question bank
exam.questions.add(question1, question2, question3)
```

### ExamAttempt
```python
attempt = ExamAttempt.objects.create(
    exam=exam,
    user=student,
    answers={
        "1": "Answer to question 1",
        "2": "B",  # MCQ option
        "3": "True"  # True/False
    }
)
```

### ExamResult
```python
result = ExamResult.objects.create(
    attempt=attempt,
    question_results={
        "1": {"correct": True, "marks_earned": 10, "difficulty": "medium"},
        "2": {"correct": False, "marks_earned": 0, "difficulty": "easy"}
    },
    correct_count=15,
    incorrect_count=3,
    unanswered_count=2,
    easy_correct=8,
    medium_correct=5,
    hard_correct=2
)
```

## 🔌 API Endpoints

### Question Bank Endpoints

#### List/Create Questions
```http
GET/POST /api/exams/questions/
Authorization: Bearer <token>
```

**Query Parameters:**
- `course_id`: Filter questions by course

**POST Request:**
```json
{
    "course": 1,
    "question_text": "What is the time complexity of binary search?",
    "question_type": "mcq",
    "difficulty": "medium",
    "options": [
        {"text": "O(n)", "is_correct": false},
        {"text": "O(log n)", "is_correct": true},
        {"text": "O(n^2)", "is_correct": false}
    ],
    "marks": 5,
    "explanation": "Binary search halves the search space each iteration",
    "tags": ["algorithms", "complexity"]
}
```

#### Question Details
```http
GET/PUT/DELETE /api/exams/questions/{id}/
```

### Exam Management Endpoints (Instructors)

#### List/Create Exams
```http
GET/POST /api/exams/
```

**POST Request:**
```json
{
    "course": 1,
    "title": "Final Exam - Python Programming",
    "description": "Comprehensive final examination",
    "total_marks": 100,
    "passing_marks": 60,
    "duration_minutes": 120,
    "questions": [1, 2, 3, 4, 5],
    "max_attempts": 2,
    "randomize_questions": true,
    "show_results_immediately": false
}
```

**Response:**
```json
{
    "id": 10,
    "title": "Final Exam - Python Programming",
    "course": 1,
    "course_title": "Python Programming",
    "total_marks": 100,
    "passing_marks": 60,
    "duration_minutes": 120,
    "question_count": 5,
    "status": "draft",
    "is_active": false
}
```

#### Exam Details
```http
GET/PUT/DELETE /api/exams/{id}/
```

#### Publish Exam
```http
POST /api/exams/{id}/publish/
```

#### Archive Exam
```http
POST /api/exams/{id}/archive/
```

### Student Exam Taking Endpoints

#### Get Course Exams
```http
GET /api/exams/course/{course_id}/
```

**Response:**
```json
[
    {
        "id": 10,
        "title": "Final Exam",
        "total_marks": 100,
        "passing_marks": 60,
        "duration_minutes": 120,
        "question_count": 20,
        "status": "published",
        "start_datetime": "2024-01-15T09:00:00Z",
        "end_datetime": "2024-01-15T18:00:00Z"
    }
]
```

#### Start Exam
```http
POST /api/exams/{exam_id}/start/
```

**Response:**
```json
{
    "attempt": {
        "id": 123,
        "exam": 10,
        "exam_title": "Final Exam",
        "started_at": "2024-01-15T10:00:00Z",
        "time_remaining": 7200,
        "status": "in_progress"
    },
    "message": "Exam attempt started successfully"
}
```

#### Submit Exam
```http
POST /api/exams/{exam_id}/submit/
```

**Request:**
```json
{
    "attempt_id": 123,
    "answers": {
        "1": "O(log n)",
        "2": "True",
        "3": "A binary tree is...",
        "4": "B"
    }
}
```

**Response:**
```json
{
    "score": 85,
    "percentage": 85,
    "passed": true,
    "total_marks": 100,
    "message": "Exam submitted successfully",
    "result": {
        "correct_count": 17,
        "incorrect_count": 3,
        "unanswered_count": 0,
        "easy_correct": 8,
        "medium_correct": 7,
        "hard_correct": 2
    }
}
```

#### Exam Attempts History
```http
GET /api/exams/{exam_id}/attempts/
```

**Response:**
```json
{
    "attempts": [
        {
            "id": 123,
            "exam_title": "Final Exam",
            "started_at": "2024-01-15T10:00:00Z",
            "completed_at": "2024-01-15T12:00:00Z",
            "score": 85,
            "percentage": 85,
            "passed": true,
            "status": "completed"
        }
    ],
    "total_attempts": 1
}
```

#### Exam Result Details
```http
GET /api/exams/attempt/{attempt_id}/result/
```

**Response:**
```json
{
    "id": 45,
    "attempt": {
        "id": 123,
        "exam_title": "Final Exam",
        "score": 85,
        "percentage": 85,
        "passed": true
    },
    "question_results": {
        "1": {
            "correct": true,
            "marks_earned": 5,
            "difficulty": "medium",
            "answer": "O(log n)"
        },
        "2": {
            "correct": false,
            "marks_earned": 0,
            "difficulty": "easy",
            "answer": "False"
        }
    },
    "correct_count": 17,
    "incorrect_count": 3,
    "unanswered_count": 0,
    "easy_correct": 8,
    "medium_correct": 7,
    "hard_correct": 2
}
```

### Instructor Analytics Endpoints

#### Exam Analytics
```http
GET /api/exams/{exam_id}/analytics/
```

**Response:**
```json
{
    "total_attempts": 45,
    "average_score": 78.5,
    "pass_rate": 84.4,
    "question_analytics": [
        {
            "question_id": 1,
            "question_text": "What is the time complexity...",
            "difficulty": "medium",
            "correct_percentage": 88.9,
            "total_attempts": 45
        },
        {
            "question_id": 2,
            "question_text": "Explain polymorphism...",
            "difficulty": "hard",
            "correct_percentage": 62.2,
            "total_attempts": 45
        }
    ]
}
```

#### All Exam Attempts (Instructor View)
```http
GET /api/exams/{exam_id}/all-attempts/
```

**Response:**
```json
{
    "attempts": [
        {
            "id": 123,
            "user_name": "John Doe",
            "started_at": "2024-01-15T10:00:00Z",
            "completed_at": "2024-01-15T12:00:00Z",
            "score": 85,
            "percentage": 85,
            "passed": true,
            "status": "completed"
        }
    ],
    "total_attempts": 45
}
```

#### Grade Manual Questions
```http
POST /api/exams/attempt/{attempt_id}/grade/
```

**Request:**
```json
{
    "manual_grades": {
        "3": 18,  // Essay question - awarded 18/20
        "5": 9    // Short answer - awarded 9/10
    }
}
```

**Response:**
```json
{
    "attempt": {
        "id": 123,
        "score": 92,
        "percentage": 92,
        "passed": true,
        "manually_graded_at": "2024-01-15T15:00:00Z",
        "graded_by": 5
    },
    "message": "Exam graded successfully"
}
```

## 🔧 Services

### Exam Services

```python
from exams.services import (
    start_exam_attempt, submit_exam_attempt,
    get_exam_analytics, grade_manual_questions
)

# Start exam
attempt = start_exam_attempt(exam, user)

# Submit exam
result = submit_exam_attempt(attempt, {
    "1": "Answer 1",
    "2": "Answer 2"
})

# Get analytics
analytics = get_exam_analytics(exam)

# Grade manual questions
graded = grade_manual_questions(
    attempt,
    manual_grades={"3": 18, "5": 9},
    graded_by=instructor
)
```

## 🧪 Testing

Run tests:
```bash
python manage.py test exams
```

Run specific test:
```bash
python manage.py test exams.tests.ExamModelTest
```

## 📈 Usage Examples

### Creating an Exam

```python
from exams.models import QuestionBank, Exam

# Create questions
q1 = QuestionBank.objects.create(
    course=course,
    question_text="What is Python?",
    question_type='mcq',
    options=[
        {"text": "Programming Language", "is_correct": True},
        {"text": "Snake", "is_correct": False}
    ],
    marks=5,
    difficulty='easy',
    created_by=instructor
)

q2 = QuestionBank.objects.create(
    course=course,
    question_text="Explain OOP principles",
    question_type='essay',
    marks=20,
    difficulty='hard',
    created_by=instructor
)

# Create exam
exam = Exam.objects.create(
    course=course,
    title="Final Exam",
    total_marks=100,
    passing_marks=60,
    duration_minutes=120,
    status='published',
    created_by=instructor
)

# Add questions
exam.questions.add(q1, q2)
```

### Taking an Exam

```python
from exams.services import start_exam_attempt, submit_exam_attempt

# Start
attempt = start_exam_attempt(exam, student)

# Submit answers
answers = {
    str(q1.id): "Programming Language",
    str(q2.id): "OOP principles include..."
}

result = submit_exam_attempt(attempt, answers)

print(f"Score: {result.score}/{result.exam.total_marks}")
print(f"Passed: {result.passed}")
```

### Grading Essays

```python
from exams.services import grade_manual_questions

# Grade essay questions manually
graded = grade_manual_questions(
    attempt,
    manual_grades={
        str(q2.id): 18  # Award 18/20 for essay
    },
    graded_by=instructor
)
```

## 🔐 Permissions

- **Students**: Can view published exams, take exams, view their results
- **Instructors**: Can create/edit exams, manage question bank, grade exams, view analytics
- **Admins**: Full access to all features

## 🚀 Roadmap

1. **Question pools** for random selection
2. **Proctoring features** (webcam, screen recording)
3. **Plagiarism detection** for essay questions
4. **Question difficulty calibration** based on performance
5. **Adaptive testing** (CAT - Computerized Adaptive Testing)
6. **Exam templates** for quick creation
7. **Question import** from external formats (QTI, Moodle)

## 📚 Related Apps

- **assessments**: For lesson-level quizzes and assignments
- **courses**: Provides course structure for exams
- **enrollments**: Tracks student access to exams
- **certificates**: Issues certificates based on exam completion

## 🤝 Contributing

When contributing:
1. Write comprehensive tests
2. Update API documentation
3. Follow Django best practices
4. Add usage examples
5. Use meaningful commit messages

## 📝 License

Part of the SkillStudio LMS project.
