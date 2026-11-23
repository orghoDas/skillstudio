from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.exceptions import ValidationError

from courses.models import Lesson
from courses.serializers import LessonCreateUpdateSerializer
from courses.views import prepare_course_edit, require_course_manager
from .models import Quiz, QuizQuestion, QuestionOption
from .serializers import ManageQuizDetailSerializer


def _coerce_int(value, field_name, errors, *, min_value=None, max_value=None, allow_empty=False):
    if allow_empty and value in (None, ''):
        return None

    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
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
    if len(title) > 255:
        errors.append('Title must be at most 255 characters.')

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

    # ASM-01: attempts allowed per student; empty/0/null = unlimited.
    if 'max_attempts' in data:
        max_attempts = data.get('max_attempts')
        if max_attempts in (None, '', 0, '0'):
            max_attempts = None
        else:
            max_attempts = _coerce_int(max_attempts, 'max_attempts', errors, min_value=1, max_value=100)
    else:
        max_attempts = quiz.max_attempts if quiz else Quiz._meta.get_field('max_attempts').default

    # ASM-04: quizzes start as drafts; publishing is an explicit choice.
    if 'is_published' in data:
        is_published = _coerce_bool(data.get('is_published'))
    else:
        is_published = quiz.is_published if quiz else False

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
                min_value=1, max_value=2147483647
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
                elif len(option_text) > 255:
                    errors.append(f'questions[{index}].options[{option_index}].text must be at most 255 characters.')

                is_correct = _coerce_bool(opt_data.get('is_correct', False))
                correct_count += 1 if is_correct else 0
                validated_options.append({
                    'text': option_text,
                    'is_correct': is_correct
                })

            if correct_count != 1:
                errors.append(f'questions[{index}] must have exactly one correct option.')

            explanation = q_data.get('explanation') or ''
            if not isinstance(explanation, str):
                errors.append(f'questions[{index}].explanation must be text.')
            difficulty = q_data.get('difficulty', QuizQuestion.Difficulty.MEDIUM)
            if difficulty not in QuizQuestion.Difficulty.values:
                errors.append(f'questions[{index}].difficulty is invalid.')

            validated_questions.append({
                'explanation': explanation,
                'difficulty': difficulty,
                'text': question_text,
                'marks': marks,
                'options': validated_options,
            })

    if validated_questions and sum(question['marks'] or 0 for question in validated_questions) > 2147483647:
        errors.append('Total marks must be at most 2147483647.')

    has_questions = bool(validated_questions) if replacing_questions else bool(quiz and quiz.questions.exists())
    if is_published and not has_questions:
        errors.append('Add at least one question before publishing this quiz.')

    return {
        'title': title,
        'passing_percentage': passing_percentage,
        'time_limit_minutes': time_limit_minutes,
        'max_attempts': max_attempts,
        'is_published': is_published,
        'questions': validated_questions,
    }, errors


class ManageQuizView(APIView):
    """Read or edit a lesson quiz as a course manager."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ManageQuizDetailSerializer, 204: None})
    def get(self, request, lesson_id):
        """Get quiz for a lesson"""
        lesson = get_object_or_404(Lesson.objects.select_related('module__course'), id=lesson_id)
        require_course_manager(request.user, lesson.module.course)
        
        quiz = Quiz.objects.filter(lesson=lesson).first()
        if not quiz:
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        return Response(ManageQuizDetailSerializer(quiz).data)

    @transaction.atomic
    def post(self, request, lesson_id):
        """Create or update quiz questions"""
        lesson = get_object_or_404(Lesson.objects.select_related('module__course'), id=lesson_id)
        prepare_course_edit(lesson.module.course, request.user)
        # Another editor could have deleted this lesson while we waited for the course lock.
        lesson = get_object_or_404(Lesson, id=lesson_id)
        quiz = Quiz.objects.select_for_update().filter(lesson=lesson).first()
        replacing_questions = 'questions' in request.data
        if quiz and replacing_questions and quiz.attempts.exists():
            transaction.set_rollback(True)
            return Response(
                {
                    'error': (
                        'Quiz questions cannot be replaced after attempts exist. '
                        'To change the questions, add a new quiz lesson.'
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        validated_data, errors = _validate_quiz_payload(request.data, lesson, quiz, replacing_questions)
        if errors:
            raise ValidationError({'non_field_errors': errors})

        if 'lesson' in request.data:
            lesson_input = request.data['lesson']
            allowed = {'title', 'content_type', 'content_text', 'duration_seconds', 'is_free', 'video_url'}
            if not isinstance(lesson_input, dict) or set(lesson_input) - allowed:
                raise ValidationError({'lesson': 'Provide only editable lesson content fields.'})
            if lesson_input.get('content_type', lesson.content_type) != 'quiz':
                raise ValidationError({'lesson': 'The lesson must use quiz content.'})
            lesson_serializer = LessonCreateUpdateSerializer(lesson, data=lesson_input, partial=True)
            lesson_serializer.is_valid(raise_exception=True)
            lesson_serializer.save()

        if quiz is None:
            quiz = Quiz.objects.create(
                lesson=lesson,
                title=validated_data['title'],
                passing_percentage=validated_data['passing_percentage'],
                time_limit_minutes=validated_data['time_limit_minutes'],
                max_attempts=validated_data['max_attempts'],
                is_published=validated_data['is_published'],
            )

        # Update quiz settings
        quiz.title = validated_data['title']
        quiz.passing_percentage = validated_data['passing_percentage']
        quiz.time_limit_minutes = validated_data['time_limit_minutes']
        quiz.max_attempts = validated_data['max_attempts']
        quiz.is_published = validated_data['is_published']

        if replacing_questions:
            # Replace questions only while there is no attempt history to preserve.
            quiz.questions.all().delete()

            for q_data in validated_data['questions']:
                question = QuizQuestion.objects.create(
                    quiz=quiz,
                    question_text=q_data['text'],
                    marks=q_data['marks'],
                    explanation=q_data['explanation'],
                    difficulty=q_data['difficulty'],
                )

                # Create options
                for opt_data in q_data['options']:
                    QuestionOption.objects.create(
                        question=question,
                        option_text=opt_data['text'],
                        is_correct=opt_data['is_correct']
                    )

        # The question signals already stored the new total; keep this instance in step.
        quiz.total_marks = quiz.compute_total_marks()
        quiz.save()

        return Response({
            'message': 'Quiz saved successfully',
            'quiz': ManageQuizDetailSerializer(quiz).data
        }, status=status.HTTP_200_OK)
