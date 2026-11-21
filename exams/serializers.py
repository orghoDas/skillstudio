from rest_framework import serializers
from django.utils.functional import cached_property
from decimal import Decimal
from .grading import MAX_EXAM_MARKS, build_questions, legacy_passing_marks, question_marks, total_question_marks
from .models import QuestionBank, Exam, ExamAttempt, ExamResult


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
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    
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

        if len(options) < 2 or any(not isinstance(option, dict) for option in options):
            raise serializers.ValidationError({'options': 'At least two options are required.'})

        if question_type == 'tf' and len(options) != 2:
            raise serializers.ValidationError({'options': 'True/false questions must have exactly two options.'})

        correct_count = sum(1 for option in options if isinstance(option, dict) and option.get('is_correct'))
        if correct_count != 1:
            raise serializers.ValidationError({'options': 'Exactly one option must be marked correct.'})
        if not question_marks(attrs.get('marks', getattr(self.instance, 'marks', 1))):
            raise serializers.ValidationError({'marks': 'Marks must be positive.'})

        return attrs


class QuestionBankListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing questions."""
    
    class Meta:
        model = QuestionBank
        fields = ['id', 'question_text', 'question_type', 'difficulty', 'marks', 'options', 'tags']


class ExamSerializer(serializers.ModelSerializer):
    """Full exam serializer with all details."""
    question_count = serializers.IntegerField(source='get_question_count', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    
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
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'status', 'total_marks']

    def validate(self, attrs):
        exam = self.instance
        course = attrs.get('course', getattr(exam, 'course', None))
        bank = attrs.get('questions')
        if bank is None:
            bank = list(exam.questions.all()) if exam else []
        custom = attrs.get('custom_questions', getattr(exam, 'custom_questions', []))

        if any(q.course_id != course.pk for q in bank):
            raise serializers.ValidationError({'questions': 'Select questions from this exam’s course.'})
        if exam and exam.attempts.exists():
            if (
                course.pk != exam.course_id
                or {q.pk for q in bank} != set(exam.questions.values_list('pk', flat=True))
                or custom != exam.custom_questions
                or any(attrs[field] != getattr(exam, field) for field in (
                    'passing_marks', 'duration_minutes', 'randomize_questions',
                ) if field in attrs)
            ):
                raise serializers.ValidationError("Create a new exam to change questions, scoring or duration after an attempt.")
            # Avoid re-setting the M2M membership from an identical PUT.
            attrs.pop('questions', None)
            return attrs

        questions = build_questions(bank, custom)
        total = total_question_marks(questions)
        if total > MAX_EXAM_MARKS or any(Decimal(q['marks']) <= 0 for q in questions):
            raise serializers.ValidationError({'questions': 'Question marks must be positive and total at most 9999.99.'})
        if not total and exam and exam.status == 'published':
            raise serializers.ValidationError({'questions': 'A published exam needs at least one question.'})

        if 'passing_marks' not in attrs:
            previous = getattr(exam, 'passing_marks', Decimal('0'))
            declared_total = getattr(exam, 'total_marks', Decimal('0'))
            attrs['passing_marks'] = legacy_passing_marks(previous, declared_total, total) if total else previous
        else:
            passing = attrs['passing_marks']
            if passing <= 0 or (total and passing > total):
                raise serializers.ValidationError({
                    'passing_marks': 'Passing marks must be greater than zero and at most the question total.'
                })

        attrs['total_marks'] = total
        return attrs

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
            if not isinstance(options, list) or len(options) < 2 or any(
                not isinstance(option, dict) for option in options
            ):
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
            if not question_marks(question.get('marks', question.get('max_marks', 1))):
                raise serializers.ValidationError(f"Custom question {index + 1} needs positive marks with at most two decimals.")

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
    """Exam as a student sees it.

    Questions come only from the student's active attempt.
    """
    questions = serializers.SerializerMethodField()
    course_name = serializers.CharField(source='course.title', read_only=True)
    custom_questions = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    questions_hidden = serializers.SerializerMethodField()
    question_order = serializers.SerializerMethodField()
    attempt = serializers.SerializerMethodField()
    
    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'course', 'course_name', 'total_marks', 'passing_marks',
            'duration_minutes', 'randomize_questions', 'questions',
            'custom_questions', 'question_order', 'max_attempts', 'start_datetime', 'end_datetime',
            'availability', 'questions_hidden', 'attempt',
        ]

    @cached_property
    def active_questions(self):
        attempt = self.context.get('attempt')
        if not attempt or attempt.status != 'in_progress' or attempt.is_expired():
            return []
        return attempt.snapshot['questions']

    def _questions(self, custom):
        return [
            {**hide_student_answer_data(question), 'options': [
                {'text': str(option.get('text', '')) if isinstance(option, dict) else str(option)}
                for option in (question['options'] or [])
            ]}
            for question in self.active_questions if question['custom'] == custom
        ]

    def get_questions(self, obj) -> list[dict]:
        return self._questions(custom=False)

    def get_custom_questions(self, obj) -> list[dict]:
        return self._questions(custom=True)

    def get_question_order(self, obj) -> list[int | str]:
        return [question['id'] for question in self.active_questions]

    def get_availability(self, obj) -> str:
        from .services import exam_availability
        return exam_availability(obj)

    def get_questions_hidden(self, obj) -> bool:
        return not self.active_questions

    def get_attempt(self, obj) -> dict | None:
        attempt = self.context.get('attempt')
        if not attempt:
            return None
        data = {'id': attempt.pk, 'status': attempt.status}
        if self.active_questions:
            data.update(
                answers=attempt.answers,
                time_remaining=attempt.time_remaining_seconds(),
                deadline=attempt.deadline.isoformat(),
                total_marks=attempt.snapshot['total_marks'],
            )
        return data


class ExamAttemptSerializer(serializers.ModelSerializer):
    """Serializer for exam attempts."""
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    time_remaining = serializers.IntegerField(source='time_remaining_seconds', read_only=True)
    total_marks = serializers.DecimalField(source='grading_total_marks', max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'user', 'user_name', 'attempt_number',
            'started_at', 'completed_at', 'time_spent_seconds', 'answers', 'score',
            'percentage', 'passed', 'status', 'time_remaining',
            'auto_graded_at', 'total_marks',
        ]
        read_only_fields = [
            'attempt_number', 'started_at', 'score', 'percentage', 'passed',
            'auto_graded_at'
        ]


class ExamAttemptListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing attempts."""
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    result = serializers.SerializerMethodField()
    total_marks = serializers.DecimalField(source='grading_total_marks', max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'attempt_number', 'started_at',
            'completed_at', 'time_spent_seconds', 'score', 'percentage', 'passed', 'status', 'result', 'total_marks',
        ]

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if not self.context.get('show_results', False):
            data.update(score=None, percentage=None, passed=None)
        return data

    def get_result(self, obj) -> dict | None:
        """Get result data if it exists."""
        if self.context.get('show_results', False) and hasattr(obj, 'result'):
            return ExamResultSerializer(obj.result, context=self.context).data
        return None


class ExamResultSerializer(serializers.ModelSerializer):
    """Serializer for detailed exam results."""
    attempt = ExamAttemptSerializer(read_only=True)
    question_results = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamResult
        fields = [
            'id', 'attempt', 'question_results', 'correct_count',
            'incorrect_count', 'unanswered_count', 'easy_correct',
            'medium_correct', 'hard_correct', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_question_results(self, result) -> dict:
        from .services import selected_option_index

        if not self.context.get('show_question_review', False):
            return {}
        attempt = result.attempt
        if attempt.snapshot is None:
            # Only the recorded grade is available for these attempts.
            return result.question_results if self.context.get('manages_exam') else {}

        review = {}
        for position, question in enumerate(attempt.snapshot['questions'], 1):
            key = str(question['id'])
            if key not in result.question_results:
                continue
            entry = result.question_results[key]
            options = question['options']
            review[key] = {
                **entry, 'position': position, 'question_text': question['question_text'],
                'options': [str(option.get('text', '')) if isinstance(option, dict) else str(option) for option in options],
                'selected_option': selected_option_index(entry.get('answer'), options),
                'correct_option': next(
                    (index for index, option in enumerate(options) if isinstance(option, dict) and option.get('is_correct')),
                    None,
                ),
            }
        return review


class ExamAnswersSerializer(serializers.Serializer):
    """Answer changes for saving or submitting an attempt."""
    attempt_id = serializers.IntegerField()
    answers = serializers.JSONField()
    
    def validate_answers(self, value):
        """Validate answers format."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Answers must be a dictionary")
        if any(answer is not None and type(answer) not in (int, str) for answer in value.values()):
            raise serializers.ValidationError("Use an option index, text answer, or null.")
        return value
