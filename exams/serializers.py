from rest_framework import serializers
from django.utils import timezone
from .models import QuestionBank, Exam, ExamAttempt, ExamResult
from accounts.serializers import UserBasicSerializer


PRIVATE_STUDENT_QUESTION_KEYS = {
    'is_correct',
    'correct_answer',
    'correct_option',
    'correct_options',
    'answer',
    'answers',
    'model_answer',
    'explanation',
}

ALLOWED_QUESTION_TYPES = {'mcq', 'tf'}


def hide_student_answer_data(value):
    if isinstance(value, list):
        return [hide_student_answer_data(item) for item in value]

    if isinstance(value, dict):
        return {
            key: hide_student_answer_data(item)
            for key, item in value.items()
            if key not in PRIVATE_STUDENT_QUESTION_KEYS
        }

    return value


class QuestionBankSerializer(serializers.ModelSerializer):
    """Serializer for question bank."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = QuestionBank
        fields = [
            'id', 'course', 'question_text', 'question_type', 'difficulty',
            'options', 'marks', 'explanation', 'tags',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def validate(self, attrs):
        question_type = attrs.get('question_type', getattr(self.instance, 'question_type', 'mcq'))
        options = attrs.get('options', getattr(self.instance, 'options', []))

        if question_type not in ALLOWED_QUESTION_TYPES:
            raise serializers.ValidationError({
                'question_type': 'Only multiple-choice and true/false questions are supported.'
            })

        if not isinstance(options, list):
            raise serializers.ValidationError({'options': 'Options must be a list.'})

        required_count = 2 if question_type == 'tf' else 2
        if len(options) < required_count:
            raise serializers.ValidationError({'options': 'At least two options are required.'})

        if question_type == 'tf' and len(options) != 2:
            raise serializers.ValidationError({'options': 'True/false questions must have exactly two options.'})

        correct_count = sum(1 for option in options if isinstance(option, dict) and option.get('is_correct'))
        if correct_count != 1:
            raise serializers.ValidationError({'options': 'Exactly one option must be marked correct.'})

        return attrs


class QuestionBankListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing questions."""
    
    class Meta:
        model = QuestionBank
        fields = ['id', 'question_text', 'question_type', 'difficulty', 'marks', 'options', 'tags']


class StudentExamQuestionSerializer(serializers.ModelSerializer):
    """Question serializer for students taking an exam."""
    options = serializers.SerializerMethodField()

    class Meta:
        model = QuestionBank
        fields = ['id', 'question_text', 'question_type', 'difficulty', 'marks', 'options', 'tags']

    def get_options(self, obj):
        return hide_student_answer_data(obj.options or [])


class ExamSerializer(serializers.ModelSerializer):
    """Full exam serializer with all details."""
    question_count = serializers.IntegerField(source='get_question_count', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Exam
        fields = [
            'id', 'course', 'title', 'description', 'total_marks', 'passing_marks',
            'duration_minutes', 'questions', 'custom_questions', 'start_datetime',
            'end_datetime', 'max_attempts', 'randomize_questions', 
            'show_results_immediately', 'show_correct_answers', 'status',
            'question_count', 'is_active', 'created_at', 'updated_at',
            'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def validate_start_datetime(self, value):
        """Ensure start_datetime is timezone-aware (UTC)."""
        if value and not timezone.is_aware(value):
            return timezone.make_aware(value, timezone.utc)
        return value
    
    def validate_end_datetime(self, value):
        """Ensure end_datetime is timezone-aware (UTC)."""
        if value and not timezone.is_aware(value):
            return timezone.make_aware(value, timezone.utc)
        return value

    def validate_custom_questions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Custom questions must be a list.")

        for index, question in enumerate(value):
            if not isinstance(question, dict):
                raise serializers.ValidationError(f"Custom question {index + 1} must be an object.")

            question_type = question.get('question_type', question.get('type', 'mcq'))
            if question_type not in ALLOWED_QUESTION_TYPES:
                raise serializers.ValidationError(
                    f"Custom question {index + 1} must be multiple-choice or true/false."
                )

            options = question.get('options', [])
            if not isinstance(options, list) or len(options) < 2:
                raise serializers.ValidationError(f"Custom question {index + 1} must have at least two options.")
            if question_type == 'tf' and len(options) != 2:
                raise serializers.ValidationError(
                    f"Custom true/false question {index + 1} must have exactly two options."
                )

            correct_count = sum(1 for option in options if isinstance(option, dict) and option.get('is_correct'))
            if correct_count != 1:
                raise serializers.ValidationError(
                    f"Custom question {index + 1} must have exactly one correct option."
                )

        return value


class ExamListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing exams."""
    question_count = serializers.IntegerField(source='get_question_count', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'course', 'course_title', 'total_marks', 'passing_marks',
            'duration_minutes', 'question_count', 'status', 'start_datetime', 'end_datetime'
        ]


class ExamDetailSerializer(serializers.ModelSerializer):
    """Detailed exam serializer with questions (for students taking exam)."""
    questions = StudentExamQuestionSerializer(many=True, read_only=True)
    course_name = serializers.CharField(source='course.title', read_only=True)
    custom_questions = serializers.SerializerMethodField()
    
    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'course', 'course_name', 'total_marks', 'passing_marks',
            'duration_minutes', 'randomize_questions', 'questions',
            'custom_questions', 'max_attempts'
        ]

    def get_custom_questions(self, obj):
        return hide_student_answer_data(obj.custom_questions or [])


class ExamAttemptSerializer(serializers.ModelSerializer):
    """Serializer for exam attempts."""
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    time_remaining = serializers.IntegerField(source='time_remaining_seconds', read_only=True)
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'user', 'user_name', 'attempt_number',
            'started_at', 'completed_at', 'time_spent_seconds', 'answers', 'score',
            'percentage', 'passed', 'status', 'time_remaining',
            'auto_graded_at'
        ]
        read_only_fields = [
            'attempt_number', 'started_at', 'score', 'percentage', 'passed',
            'auto_graded_at'
        ]


class ExamAttemptListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing attempts."""
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    result = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'attempt_number', 'started_at',
            'completed_at', 'score', 'percentage', 'passed', 'status', 'result'
        ]
    
    def get_result(self, obj):
        """Get result data if it exists."""
        if hasattr(obj, 'result'):
            return ExamResultSerializer(obj.result).data
        return None


class ExamResultSerializer(serializers.ModelSerializer):
    """Serializer for detailed exam results."""
    attempt = ExamAttemptSerializer(read_only=True)
    
    class Meta:
        model = ExamResult
        fields = [
            'id', 'attempt', 'question_results', 'correct_count',
            'incorrect_count', 'unanswered_count', 'easy_correct',
            'medium_correct', 'hard_correct', 'created_at'
        ]
        read_only_fields = ['created_at']


class SubmitExamSerializer(serializers.Serializer):
    """Serializer for submitting exam answers."""
    attempt_id = serializers.IntegerField()
    answers = serializers.JSONField()
    
    def validate_answers(self, value):
        """Validate answers format."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Answers must be a dictionary")
        return value
