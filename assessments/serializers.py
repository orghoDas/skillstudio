from rest_framework import serializers
from .models import (
    Quiz,
    QuizQuestion,
    QuestionOption,
    QuizAttempt,
)


# ===============================
# QUIZ SERIALIZERS
# ===============================

class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "option_text"]


class ManageQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "option_text", "is_correct"]


class QuizQuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True)

    class Meta:
        model = QuizQuestion
        fields = [
            "id",
            "question_text",
            "difficulty",
            "marks",
            "options"
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "time_limit_minutes",
            "total_marks",
            "questions"
        ]


class ManageQuizQuestionSerializer(serializers.ModelSerializer):
    options = ManageQuestionOptionSerializer(many=True)

    class Meta:
        model = QuizQuestion
        fields = [
            "id",
            "question_text",
            "difficulty",
            "marks",
            "options",
        ]


class ManageQuizDetailSerializer(serializers.ModelSerializer):
    questions = ManageQuizQuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "time_limit_minutes",
            "passing_percentage",
            "is_published",
            "total_marks",
            "questions",
        ]


class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "started_at",
            "completed_at",
            "score",
            "passed"
        ]
