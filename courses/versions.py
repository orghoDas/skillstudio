from decimal import Decimal

from django.db.models import Max

from .models import Course, CourseTag, CourseVersion, Lesson, LessonResource, Module


COURSE_FIELDS = ('title', 'description', 'category_id', 'price', 'is_free', 'thumbnail', 'level')
LESSON_FIELDS = ('title', 'position', 'content_type', 'content_text', 'video_url', 'duration_seconds', 'metadata', 'is_free')


def _fields(obj, names):
    return {name: getattr(obj, name) for name in names}


def snapshot_course(course):
    details = _fields(course, COURSE_FIELDS)
    details['price'] = str(details['price'])
    return {
        'course': details,
        'tag_ids': list(course.tags.values_list('pk', flat=True)),
        'modules': [
            {
                **_fields(module, ('title', 'position')),
                'lessons': [
                    {
                        **_fields(lesson, LESSON_FIELDS),
                        'source_id': lesson.pk,
                        'resources': [_fields(resource, ('file_url', 'resource_type')) for resource in lesson.resources.all()],
                    }
                    for lesson in module.lessons.all()
                ],
            }
            for module in course.modules.prefetch_related('lessons__resources')
        ],
    }


def record_published_version(course, data=None):
    number = course.versions.aggregate(latest=Max('version_number'))['latest'] or 0
    if course.revision_of_id and course.revision_of.current_version_id:
        number = max(number, course.revision_of.current_version.version_number)
    return CourseVersion.objects.create(
        course=course, version_number=number + 1,
        data=snapshot_course(course) if data is None else data,
    )


def copy_course_draft(source, data):
    fields = {**data['course'], 'price': Decimal(data['course']['price'])}
    draft = Course.objects.create(instructor_id=source.instructor_id, revision_of=source, **fields)
    CourseTag.objects.bulk_create([CourseTag(course=draft, tag_id=pk) for pk in data['tag_ids']])
    lesson_map = {}
    for section in data['modules']:
        module = Module.objects.create(course=draft, title=section['title'], position=section['position'])
        for item in section['lessons']:
            lesson = Lesson.objects.create(module=module, **{name: item[name] for name in LESSON_FIELDS})
            lesson_map[item['source_id']] = lesson
            LessonResource.objects.bulk_create([
                LessonResource(lesson=lesson, **resource) for resource in item['resources']
            ])

    _copy_quizzes(lesson_map)
    _copy_exams(source, draft)
    return draft


def _copy_quizzes(lesson_map):
    from assessments.models import Quiz, QuizQuestion, QuestionOption

    quizzes = Quiz.objects.filter(lesson_id__in=lesson_map).prefetch_related('questions__options')
    for original in quizzes:
        quiz = Quiz.objects.create(
            lesson=lesson_map[original.lesson_id],
            **_fields(original, ('title', 'time_limit_minutes', 'passing_percentage', 'is_published', 'max_attempts')),
        )
        for item in original.questions.all():
            question = QuizQuestion.objects.create(quiz=quiz, **_fields(item, ('question_text', 'difficulty', 'marks', 'explanation')))
            QuestionOption.objects.bulk_create([
                QuestionOption(question=question, **_fields(option, ('option_text', 'is_correct')))
                for option in item.options.all()
            ])
        quiz.refresh_total_marks()


def _copy_exams(source, draft):
    from exams.models import Exam, QuestionBank

    question_map = {}
    for original in source.question_bank.all():
        question_map[original.pk] = QuestionBank.objects.create(
            course=draft, **_fields(original, (
                'question_text', 'question_type', 'difficulty', 'options', 'marks', 'explanation', 'tags', 'created_by_id',
            )),
        )
    for original in source.exams.prefetch_related('questions'):
        exam = Exam.objects.create(
            course=draft, status='draft', **_fields(original, (
                'title', 'description', 'total_marks', 'passing_marks', 'duration_minutes', 'custom_questions',
                'start_datetime', 'end_datetime', 'max_attempts', 'randomize_questions', 'show_results_immediately',
                'show_correct_answers', 'created_by_id',
            )),
        )
        exam.questions.set(question_map[q.pk] for q in original.questions.all() if q.pk in question_map)
