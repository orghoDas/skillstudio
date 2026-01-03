from rest_framework import serializers
from .models import QuestionBank, Exam, ExamAttempt, ExamResult
from accounts.serializers import UserBasicSerializer


class QuestionBankSerializer(serializers.ModelSerializer):
    """Serializer for question bank."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = QuestionBank
        fields = [
            'id', 'course', 'question_text', 'question_type', 'difficulty',
            'options', 'correct_answer', 'marks', 'explanation', 'tags',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class QuestionBankListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing questions."""
    
    class Meta:
        model = QuestionBank
        fields = ['id', 'question_text', 'question_type', 'difficulty', 'marks', 'tags']


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
    questions_data = QuestionBankListSerializer(source='questions', many=True, read_only=True)
    
    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'total_marks', 'passing_marks',
            'duration_minutes', 'randomize_questions', 'questions_data',
            'custom_questions', 'max_attempts'
        ]


class ExamAttemptSerializer(serializers.ModelSerializer):
    """Serializer for exam attempts."""
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    time_remaining = serializers.IntegerField(source='time_remaining_seconds', read_only=True)
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'user', 'user_name', 'started_at',
            'completed_at', 'time_spent_seconds', 'answers', 'score',
            'percentage', 'passed', 'status', 'time_remaining',
            'auto_graded_at', 'manually_graded_at', 'graded_by'
        ]
        read_only_fields = [
            'started_at', 'score', 'percentage', 'passed',
            'auto_graded_at', 'manually_graded_at'
        ]


class ExamAttemptListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing attempts."""
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'started_at', 'completed_at',
            'score', 'percentage', 'passed', 'status'
        ]


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
