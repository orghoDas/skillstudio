from django.contrib import admin
from .models import Assessment, Question, Choice, Submission, Answer

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_published", "opens_at", "closes_at")
    list_filter = ("is_published",)
    search_fields = ("title",)

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1

class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "assessment", "position", "question_type", "points")
    list_filter = ("question_type",)
    inlines = [ChoiceInline]

admin.site.register(Question, QuestionAdmin)
admin.site.register(Choice)
admin.site.register(Submission)
admin.site.register(Answer)
