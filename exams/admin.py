from django.contrib import admin
from .models import QuestionBank, Exam, ExamAttempt, ExamResult


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    """Admin interface for Question Bank."""
    list_display = ['id', 'question_text_short', 'question_type', 'difficulty', 'marks', 'course', 'created_at']
    list_filter = ['question_type', 'difficulty', 'course', 'created_at']
    search_fields = ['question_text', 'tags']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Question Details', {
            'fields': ('course', 'question_text', 'question_type', 'difficulty', 'marks')
        }),
        ('Answer Options', {
            'fields': ('options', 'correct_answer', 'explanation')
        }),
        ('Metadata', {
            'fields': ('tags', 'created_by', 'created_at', 'updated_at')
        }),
    )
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    """Admin interface for Exams."""
    list_display = ['id', 'title', 'course', 'status', 'total_marks', 'duration_minutes', 'question_count_display', 'created_at']
    list_filter = ['status', 'course', 'created_at', 'start_datetime']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['created_at', 'updated_at', 'get_question_count']
    filter_horizontal = ['questions']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('course', 'title', 'description', 'status')
        }),
        ('Scoring', {
            'fields': ('total_marks', 'passing_marks')
        }),
        ('Timing', {
            'fields': ('duration_minutes', 'start_datetime', 'end_datetime')
        }),
        ('Questions', {
            'fields': ('questions', 'custom_questions')
        }),
        ('Settings', {
            'fields': ('max_attempts', 'randomize_questions', 'show_results_immediately', 'show_correct_answers')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def question_count_display(self, obj):
        return obj.get_question_count()
    question_count_display.short_description = 'Questions'


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    """Admin interface for Exam Attempts."""
    list_display = ['id', 'user_email', 'exam_title', 'score', 'percentage', 'passed', 'status', 'started_at', 'completed_at']
    list_filter = ['status', 'passed', 'exam', 'started_at']
    search_fields = ['user__email', 'exam__title']
    readonly_fields = ['started_at', 'time_remaining_seconds', 'auto_graded_at', 'manually_graded_at']
    
    fieldsets = (
        ('Attempt Info', {
            'fields': ('exam', 'user', 'status')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'time_spent_seconds', 'time_remaining_seconds')
        }),
        ('Answers & Scoring', {
            'fields': ('answers', 'score', 'percentage', 'passed')
        }),
        ('Grading', {
            'fields': ('auto_graded_at', 'manually_graded_at', 'graded_by')
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def exam_title(self, obj):
        return obj.exam.title
    exam_title.short_description = 'Exam'


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    """Admin interface for Exam Results."""
    list_display = ['id', 'attempt_user', 'attempt_exam', 'correct_count', 'incorrect_count', 'unanswered_count', 'created_at']
    list_filter = ['created_at', 'attempt__exam']
    search_fields = ['attempt__user__email', 'attempt__exam__title']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Attempt', {
            'fields': ('attempt',)
        }),
        ('Summary', {
            'fields': ('correct_count', 'incorrect_count', 'unanswered_count')
        }),
        ('Difficulty Breakdown', {
            'fields': ('easy_correct', 'medium_correct', 'hard_correct')
        }),
        ('Detailed Results', {
            'fields': ('question_results',)
        }),
    )
    
    def attempt_user(self, obj):
        return obj.attempt.user.email
    attempt_user.short_description = 'User'
    
    def attempt_exam(self, obj):
        return obj.attempt.exam.title
    attempt_exam.short_description = 'Exam'

