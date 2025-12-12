from django.contrib import admin
from .models import Quiz, QuizQuestion, QuestionOption, QuizAttempt, Assignment, Submission


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "lesson", "total_marks", "time_limit_minutes")
    search_fields = ("title",)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 2


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "question_type", "difficulty")
    list_filter = ("question_type", "difficulty")
    inlines = [QuestionOptionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "user", "started_at", "completed_at", "score")
    list_filter = ("completed_at",)
    search_fields = ("user__email",)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "lesson", "due_date", "created_at")
    search_fields = ("title",)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "assignment", "user", "submitted_at", "grade", "graded_at")
    list_filter = ("graded_at",)
    search_fields = ("user__email",)
