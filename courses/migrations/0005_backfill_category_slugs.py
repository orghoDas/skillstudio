from itertools import count

from django.db import migrations, models
from django.utils.text import slugify


def fill_empty_category_slugs(apps, schema_editor):
    Category = apps.get_model('courses', 'Category')
    categories = Category.objects.using(schema_editor.connection.alias)
    for category in categories.filter(slug=''):
        base = slugify(category.name) or 'category'
        for number in count():
            suffix = f'-{number}' if number else ''
            candidate = f'{base[:100 - len(suffix)]}{suffix}'
            if not categories.filter(slug=candidate).exists():
                categories.filter(pk=category.pk).update(slug=candidate)
                break


class Migration(migrations.Migration):
    dependencies = [('courses', '0004_course_revisions')]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(blank=True, max_length=100, unique=True),
        ),
        migrations.RunPython(fill_empty_category_slugs, migrations.RunPython.noop),
    ]
