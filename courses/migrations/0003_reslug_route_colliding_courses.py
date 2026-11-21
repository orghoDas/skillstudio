# API-02: a course whose slug is purely numeric (e.g. "2024") or a reserved
# route word (e.g. "tags") was unreachable by slug: /api/courses/2024/ resolves
# to the course with *id* 2024, and /api/courses/tags/ is the tags endpoint.
# Give such courses a non-colliding slug ("2024-course", "tags-course", made
# unique with -1, -2, ... if needed). New courses get this from Course.save().

from django.db import migrations

RESERVED = {'admin', 'categories', 'create', 'instructor', 'lessons', 'modules', 'sections', 'tags'}


def reslug_colliding_courses(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    for course in Course.objects.all().iterator():
        slug = course.slug or ""
        if slug and not slug.isdigit() and slug not in RESERVED:
            continue
        base = f"{slug or 'course'}-course"
        candidate, counter = base, 1
        while Course.objects.filter(slug=candidate).exclude(pk=course.pk).exists():
            candidate = f"{base}-{counter}"
            counter += 1
        Course.objects.filter(pk=course.pk).update(slug=candidate)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_alter_lesson_metadata'),
    ]

    operations = [
        migrations.RunPython(reslug_colliding_courses, migrations.RunPython.noop),
    ]
