from django.contrib import admin
from .models import Quiz, QuizQuestion, QuestionOption, QuizAttempt


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "lesson", "total_marks", "time_limit_minutes")
    search_fields = ("title",)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 2


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "difficulty")
    list_filter = ("difficulty",)
    inlines = [QuestionOptionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "user", "started_at", "completed_at", "score")
    list_filter = ("completed_at",)
    search_fields = ("user__email",)
