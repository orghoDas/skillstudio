from django.contrib import admin
from django.core.exceptions import ValidationError
from core.admin import ReadOnlyAdmin, WorkflowAdmin
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
class QuizAttemptAdmin(WorkflowAdmin):
    list_display = ("id", "quiz", "user", "started_at", "completed_at", "score")
    list_filter = ("completed_at",)
    search_fields = ("user__email",)

    decision_help = "Grant one extra try while retaining this attempt and its score."

    def workflow_choices(self, obj):
        if obj.completed_at and not obj.passed and not obj.retry_granted and obj.quiz.max_attempts is not None:
            return [('grant_retry', 'Grant extra attempt')]
        return []

    def decision_details(self, obj):
        return [('Student', obj.user.email), ('Quiz', obj.quiz.title), ('Attempt', obj.attempt_number)]

    def apply_decision(self, request, obj, data):
        quiz = Quiz.objects.select_for_update().get(pk=obj.quiz_id)
        attempt = QuizAttempt.objects.select_for_update().get(pk=obj.pk)
        attempt.quiz = quiz
        if not self.workflow_choices(attempt):
            raise ValidationError('This attempt is no longer eligible for a retry.')
        attempt.retry_granted = True
        attempt.save(update_fields=['retry_granted'])
        note = data['note']
        return f'Granted an extra quiz attempt. {note}'.strip()
