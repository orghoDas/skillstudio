from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from accounts.models import User
from courses.models import Course


class QuestionBank(models.Model):
    """
    Question bank for storing reusable exam questions.
    Questions can be tagged and filtered for exam creation.
    """
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('tf', 'True/False'),
        ('short', 'Short Answer'),
        ('essay', 'Essay'),
    ]
    
    DIFFICULTIES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='question_bank')
    question_text = models.TextField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default='mcq')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES, default='medium')
    
    # For MCQ and True/False
    options = models.JSONField(default=list, blank=True)  # [{"text": "Option A", "is_correct": true}]
    correct_answer = models.TextField(blank=True)  # For short answer/essay model answers
    
    # Metadata
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    explanation = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)  # ["python", "loops", "basics"]
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_questions')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.question_text[:50]}... ({self.get_difficulty_display()})"

# PostgreSQL equivalent for question bank:
# CREATE TABLE IF NOT EXISTS exams_questionbank (
#     id serial PRIMARY KEY,
#     course_id integer NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     question_text text NOT NULL,
#     question_type varchar(10) NOT NULL DEFAULT 'mcq',
#     difficulty varchar(10) NOT NULL DEFAULT 'medium',
#     options jsonb NOT NULL DEFAULT '[]',
#     correct_answer text NOT NULL DEFAULT '',
#     marks numeric(5,2) NOT NULL DEFAULT 1,
#     explanation text NOT NULL DEFAULT '',
#     tags jsonb NOT NULL DEFAULT '[]',
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now(),
#     created_by_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL
# );


class Exam(models.Model):
    """
    Final exam for a course. Can pull questions from QuestionBank.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='exams')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Exam settings
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    passing_marks = models.DecimalField(max_digits=6, decimal_places=2, default=50)
    duration_minutes = models.IntegerField(validators=[MinValueValidator(1)])
    
    # Questions (selected from QuestionBank or custom)
    questions = models.ManyToManyField(QuestionBank, related_name='exams', blank=True)
    custom_questions = models.JSONField(default=list, blank=True)  # For one-time questions
    
    # Scheduling
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    
    # Attempt settings
    max_attempts = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    randomize_questions = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=True)
    show_correct_answers = models.BooleanField(default=False)
    
    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_exams')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.course.title}"
    
    def is_active(self):
        """Check if exam is currently available."""
        now = timezone.now()
        if self.status != 'published':
            return False
        if self.start_datetime and now < self.start_datetime:
            return False
        if self.end_datetime and now > self.end_datetime:
            return False
        return True
    
    def get_question_count(self):
        """Get total number of questions."""
        return self.questions.count() + len(self.custom_questions)


# PostgreSQL equivalent for exams:
# CREATE TABLE IF NOT EXISTS exams_exam (
#     id serial PRIMARY KEY,
#     course_id integer NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     title varchar(255) NOT NULL,
#     description text NOT NULL DEFAULT '',
#     total_marks numeric(6,2) NOT NULL DEFAULT 100,
#     passing_marks numeric(6,2) NOT NULL DEFAULT 50,
#     duration_minutes integer NOT NULL,
#     custom_questions jsonb NOT NULL DEFAULT '[]',
#     start_datetime timestamptz NULL,
#     end_datetime timestamptz NULL,
#     max_attempts integer NOT NULL DEFAULT 1,
#     randomize_questions boolean NOT NULL DEFAULT false,
#     show_results_immediately boolean NOT NULL DEFAULT true,
#     show_correct_answers boolean NOT NULL DEFAULT false,
#     status varchar(10) NOT NULL DEFAULT 'draft',
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now(),
#     created_by_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL
# );
# -- Many-to-many table for exam questions (auto-generated by Django):
# CREATE TABLE IF NOT EXISTS exams_exam_questions (
#     id serial PRIMARY KEY,
#     exam_id integer NOT NULL REFERENCES exams_exam(id) ON DELETE CASCADE,
#     questionbank_id integer NOT NULL REFERENCES exams_questionbank(id) ON DELETE CASCADE
# );


class ExamAttempt(models.Model):
    """
    Student's attempt at an exam.
    """
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.IntegerField(default=0)
    
    # Answers and scoring
    answers = models.JSONField(default=dict)  # {question_id: answer}
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    
    # Grading (for manual grading of essay questions)
    auto_graded_at = models.DateTimeField(null=True, blank=True)
    manually_graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_exam_attempts')
    
    class Meta:
        ordering = ['-started_at']
        unique_together = [['exam', 'user', 'started_at']]
    
    def __str__(self):
        return f"{self.user.email} - {self.exam.title} - {self.started_at}"
    
    def is_expired(self):
        """Check if attempt time has expired."""
        if self.completed_at:
            return False
        if not self.exam.duration_minutes:
            return False
        
        expiry_time = self.started_at + timedelta(minutes=self.exam.duration_minutes)
        return timezone.now() > expiry_time
    
    def time_remaining_seconds(self):
        """Calculate remaining time in seconds."""
        if self.completed_at or not self.exam.duration_minutes:
            return None
        
        expiry_time = self.started_at + timedelta(minutes=self.exam.duration_minutes)
        remaining = (expiry_time - timezone.now()).total_seconds()
        return max(0, int(remaining))
    
    def calculate_score(self):
        """Calculate and save score from answers."""
        if not self.answers:
            self.score = Decimal('0')
            self.percentage = Decimal('0')
            self.passed = False
            return
        
        total_score = Decimal('0')
        total_possible = self.exam.total_marks
        
        # Auto-grade MCQ and True/False questions
        for question in self.exam.questions.filter(question_type__in=['mcq', 'tf']):
            q_id = str(question.id)
            answer = self.answers.get(q_id)
            
            # Answer is the index of the selected option (0-based)
            if answer is not None and answer != '':
                answer_idx = int(answer) if isinstance(answer, str) else answer
                options = question.options or []
                
                # Check if the selected option is correct
                if 0 <= answer_idx < len(options):
                    selected_option = options[answer_idx]
                    if selected_option.get('is_correct', False):
                        total_score += question.marks
        
        self.score = total_score
        self.percentage = (total_score / total_possible * 100) if total_possible > 0 else Decimal('0')
        self.passed = self.score >= self.exam.passing_marks
        self.auto_graded_at = timezone.now()
        self.save()


    # PostgreSQL equivalent for exam attempts:
    # CREATE TABLE IF NOT EXISTS exams_examattempt (
    #     id serial PRIMARY KEY,
    #     exam_id integer NOT NULL REFERENCES exams_exam(id) ON DELETE CASCADE,
    #     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    #     started_at timestamptz NOT NULL DEFAULT now(),
    #     completed_at timestamptz NULL,
    #     time_spent_seconds integer NOT NULL DEFAULT 0,
    #     answers jsonb NOT NULL DEFAULT '{}',
    #     score numeric(6,2) NULL,
    #     percentage numeric(5,2) NULL,
    #     passed boolean NULL,
    #     status varchar(20) NOT NULL DEFAULT 'in_progress',
    #     auto_graded_at timestamptz NULL,
    #     manually_graded_at timestamptz NULL,
    #     graded_by_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL,
    #     UNIQUE (exam_id, user_id, started_at)
    # );
    # CREATE INDEX IF NOT EXISTS idx_exams_examattempt_started ON exams_examattempt (started_at DESC);


class ExamResult(models.Model):
    """
    Detailed results breakdown for an exam attempt.
    """
    attempt = models.OneToOneField(ExamAttempt, on_delete=models.CASCADE, related_name='result')
    
    # Question-wise breakdown
    question_results = models.JSONField(default=dict)  # {question_id: {correct: bool, marks_earned: float}}
    
    # Performance metrics
    correct_count = models.IntegerField(default=0)
    incorrect_count = models.IntegerField(default=0)
    unanswered_count = models.IntegerField(default=0)
    
    # Difficulty-wise performance
    easy_correct = models.IntegerField(default=0)
    medium_correct = models.IntegerField(default=0)
    hard_correct = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Result for {self.attempt}"

# PostgreSQL equivalent for exam results:
# CREATE TABLE IF NOT EXISTS exams_examresult (
#     id serial PRIMARY KEY,
#     attempt_id integer NOT NULL UNIQUE REFERENCES exams_examattempt(id) ON DELETE CASCADE,
#     question_results jsonb NOT NULL DEFAULT '{}',
#     correct_count integer NOT NULL DEFAULT 0,
#     incorrect_count integer NOT NULL DEFAULT 0,
#     unanswered_count integer NOT NULL DEFAULT 0,
#     easy_correct integer NOT NULL DEFAULT 0,
#     medium_correct integer NOT NULL DEFAULT 0,
#     hard_correct integer NOT NULL DEFAULT 0,
#     created_at timestamptz NOT NULL DEFAULT now()
# );
