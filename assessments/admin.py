from django.contrib import admin
from core.admin import ReadOnlyAdmin
from .models import Quiz, QuizQuestion, QuestionOption, QuizAttempt


@admin.register(Quiz)
class QuizAdmin(ReadOnlyAdmin):
    list_display = ("id", "title", "lesson", "total_marks", "time_limit_minutes")
    search_fields = ("title",)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 0
    can_delete = False
    readonly_fields = ("option_text", "is_correct")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(QuizQuestion)
class QuizQuestionAdmin(ReadOnlyAdmin):
    list_display = ("id", "quiz", "difficulty")
    list_filter = ("difficulty",)
    inlines = [QuestionOptionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(ReadOnlyAdmin):
    list_display = ("id", "quiz", "user", "started_at", "completed_at", "score")
    list_filter = ("completed_at",)
    search_fields = ("user__email",)
