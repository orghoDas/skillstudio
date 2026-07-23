from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction

from courses.models import Lesson
from .models import Quiz, QuizQuestion, QuestionOption
from .serializers import ManageQuizDetailSerializer


def _coerce_int(value, field_name, errors, *, min_value=None, max_value=None, allow_empty=False):
    if allow_empty and value in (None, ''):
        return None

    if isinstance(value, bool):
        errors.append(f'{field_name} must be an integer.')
        return None

    try:
        number = int(value)
    except (TypeError, ValueError):
        errors.append(f'{field_name} must be an integer.')
        return None

    if min_value is not None and number < min_value:
        errors.append(f'{field_name} must be at least {min_value}.')
    if max_value is not None and number > max_value:
        errors.append(f'{field_name} must be at most {max_value}.')

    return number


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _validate_quiz_payload(data, lesson, quiz, replacing_questions):
    errors = []

    title = data.get('title', quiz.title if quiz else f'{lesson.title} Quiz')
    title = str(title).strip() if title is not None else ''
    if not title:
        title = quiz.title if quiz else f'{lesson.title} Quiz'

    passing_percentage = data.get(
        'passing_percentage',
        quiz.passing_percentage if quiz else 50
    )
    passing_percentage = _coerce_int(
        passing_percentage,
        'passing_percentage',
        errors,
        min_value=0,
        max_value=100
    )

    time_limit_minutes = data.get(
        'time_limit_minutes',
        quiz.time_limit_minutes if quiz else None
    )
    if time_limit_minutes in (None, '', 0, '0'):
        time_limit_minutes = None
    else:
        time_limit_minutes = _coerce_int(
            time_limit_minutes,
            'time_limit_minutes',
            errors,
            min_value=1
        )

    validated_questions = None
    if replacing_questions:
        questions_data = data.get('questions', [])
        if not isinstance(questions_data, list):
            errors.append('questions must be a list.')
            questions_data = []

        validated_questions = []
        for index, q_data in enumerate(questions_data):
            if not isinstance(q_data, dict):
                errors.append(f'questions[{index}] must be an object.')
                continue

            question_text = q_data.get('text', q_data.get('question_text', ''))
            question_text = str(question_text).strip() if question_text is not None else ''
            if not question_text:
                errors.append(f'questions[{index}].text is required.')

            question_type = q_data.get('type', q_data.get('question_type', 'mcq'))
            if question_type not in (None, '', 'mcq'):
                errors.append(f'questions[{index}].type must be mcq.')

            marks = _coerce_int(
                q_data.get('marks', 1),
                f'questions[{index}].marks',
                errors,
                min_value=1
            )

            options_data = q_data.get('options', [])
            if not isinstance(options_data, list):
                errors.append(f'questions[{index}].options must be a list.')
                options_data = []

            if len(options_data) < 2:
                errors.append(f'questions[{index}].options must contain at least 2 options.')

            validated_options = []
            correct_count = 0
            for option_index, opt_data in enumerate(options_data):
                if not isinstance(opt_data, dict):
                    errors.append(f'questions[{index}].options[{option_index}] must be an object.')
                    continue

                option_text = opt_data.get('text', opt_data.get('option_text', ''))
                option_text = str(option_text).strip() if option_text is not None else ''
                if not option_text:
                    errors.append(f'questions[{index}].options[{option_index}].text is required.')

                is_correct = _coerce_bool(opt_data.get('is_correct', False))
                correct_count += 1 if is_correct else 0
                validated_options.append({
                    'text': option_text,
                    'is_correct': is_correct
                })

            if correct_count != 1:
                errors.append(f'questions[{index}] must have exactly one correct option.')

            validated_questions.append({
                'text': question_text,
                'marks': marks,
                'options': validated_options,
            })

    return {
        'title': title,
        'passing_percentage': passing_percentage,
        'time_limit_minutes': time_limit_minutes,
        'questions': validated_questions,
    }, errors


class ManageQuizView(APIView):
    """Create or update quiz for a lesson (instructor only)"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        """Get quiz for a lesson"""
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Check if user is the instructor
        if lesson.module.course.instructor != request.user:
            return Response(
                {'error': 'You do not have permission to access this quiz'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        quiz = Quiz.objects.filter(lesson=lesson).first()
        if not quiz:
            return Response(
                {'error': 'Quiz not found for this lesson.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(ManageQuizDetailSerializer(quiz).data)

    @transaction.atomic
    def post(self, request, lesson_id):
        """Create or update quiz questions"""
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Check if user is the instructor
        if lesson.module.course.instructor != request.user:
            return Response(
                {'error': 'You do not have permission to manage this quiz'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        quiz = Quiz.objects.filter(lesson=lesson).first()
        replacing_questions = 'questions' in request.data
        if quiz and replacing_questions and quiz.attempts.exists():
            return Response(
                {
                    'error': (
                        'Quiz questions cannot be replaced after attempts exist. '
                        'Create a new quiz version instead.'
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        validated_data, errors = _validate_quiz_payload(request.data, lesson, quiz, replacing_questions)
        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        if quiz is None:
            quiz = Quiz.objects.create(
                lesson=lesson,
                title=validated_data['title'],
                passing_percentage=validated_data['passing_percentage'],
                time_limit_minutes=validated_data['time_limit_minutes']
            )

        # Update quiz settings
        quiz.title = validated_data['title']
        quiz.passing_percentage = validated_data['passing_percentage']
        quiz.time_limit_minutes = validated_data['time_limit_minutes']

        if replacing_questions:
            # Replace questions only while there is no attempt history to preserve.
            quiz.questions.all().delete()

            total_marks = 0

            for q_data in validated_data['questions']:
                question = QuizQuestion.objects.create(
                    quiz=quiz,
                    question_text=q_data['text'],
                    marks=q_data['marks']
                )
                total_marks += question.marks

                # Create options
                for opt_data in q_data['options']:
                    QuestionOption.objects.create(
                        question=question,
                        option_text=opt_data['text'],
                        is_correct=opt_data['is_correct']
                    )

            # Update total marks
            quiz.total_marks = total_marks

        quiz.save()

        return Response({
            'message': 'Quiz saved successfully',
            'quiz': ManageQuizDetailSerializer(quiz).data
        }, status=status.HTTP_200_OK)
