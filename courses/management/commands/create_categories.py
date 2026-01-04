from django.core.management.base import BaseCommand
from courses.models import Category


class Command(BaseCommand):
    help = 'Create default course categories'

    def handle(self, *args, **kwargs):
        categories = [
            ('Programming', 'programming'),
            ('Design', 'design'),
            ('Business', 'business'),
            ('Marketing', 'marketing'),
            ('Data Science', 'data-science'),
            ('Other', 'other')
        ]

        for name, slug in categories:
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={'slug': slug}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created category: {name}'))
            else:
                self.stdout.write(f'Category already exists: {name}')

        self.stdout.write(self.style.SUCCESS('Categories setup complete!'))
