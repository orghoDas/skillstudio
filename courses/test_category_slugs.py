from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connection, connections, models
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from courses.models import Category, Course


class CategorySlugTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(email='category-admin@example.test', password='test-password')

    def test_api_generates_distinct_slugs_and_refuses_duplicate_names(self):
        self.client.force_authenticate(self.admin)
        url = '/api/courses/categories/create/'
        first = self.client.post(url, {'name': 'Web & Design', 'slug': 'ignored'}, format='json')
        second = self.client.post(url, {'name': 'Web Design'}, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual((first.data['slug'], second.data['slug']), ('web-design', 'web-design-1'))
        self.assertEqual(second.data['course_count'], 0)
        self.assertEqual(self.client.post(url, {'name': 'Web Design'}, format='json').status_code, 400)

        created = Category.objects.get(pk=second.data['id'])
        created.name = 'Design Fundamentals'
        created.save(update_fields=['name'])
        created.refresh_from_db()
        self.assertEqual(created.slug, 'web-design-1')

    def test_fallback_and_suffix_fit_slug_length(self):
        fallback = Category.objects.create(name='বাংলা')
        Category.objects.create(name='A' * 100)
        collision = Category.objects.create(name='a' * 100)
        self.assertEqual(fallback.slug, 'category')
        self.assertEqual(collision.slug, 'a' * 98 + '-1')

    def test_admin_accepts_a_blank_slug_and_can_keep_a_custom_one(self):
        self.client.force_login(self.admin)
        url = reverse('admin:courses_category_add')
        for name, slug in (('Admin Category', ''), ('Admin & Category', ''), ('Other Topic', 'custom-topic')):
            with self.subTest(name=name):
                response = self.client.post(url, {'name': name, 'slug': slug}, secure=True)
                self.assertEqual(response.status_code, 302)
        self.assertEqual(Category.objects.get(name='Admin Category').slug, 'admin-category')
        self.assertEqual(Category.objects.get(name='Admin & Category').slug, 'admin-category-1')
        self.assertEqual(Category.objects.get(name='Other Topic').slug, 'custom-topic')

    def test_category_list_counts_published_courses_in_a_fixed_number_of_queries(self):
        first = Category.objects.create(name='Category with courses')
        second = Category.objects.create(name='Empty category')
        for status in ('draft', 'published', 'published', 'archived'):
            Course.objects.create(title='Course title', category=first, status=status, instructor=self.admin)

        with self.assertNumQueries(2):
            response = self.client.get('/api/courses/categories/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['id']: row['course_count'] for row in response.data['results']}, {
            first.pk: 2, second.pk: 0,
        })
        listed = self.client.get('/api/courses/', {'category': first.slug})
        self.assertEqual(listed.data['count'], 2)


class CategorySlugMigrationTests(TransactionTestCase):
    previous = [('courses', '0004_course_revisions')]
    target = [('courses', '0005_backfill_category_slugs')]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_backfill_repairs_empty_slug_and_leaves_an_existing_slug_in_place(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        apps = executor.loader.project_state(self.previous).apps
        historical = apps.get_model('courses', 'Category').objects
        stable = historical.create(name='Legacy Design', slug='web-design')
        broken = historical.create(name='Web Design', slug='')
        MigrationExecutor(connection).migrate(self.target)
        self.assertEqual(Category.objects.get(pk=stable.pk).slug, 'web-design')
        self.assertEqual(Category.objects.get(pk=broken.pk).slug, 'web-design-1')


class CategorySlugConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_inserts_retry_slug_collisions_and_reject_duplicate_names(self):
        admin = User.objects.create_user(email='category-race@example.test', role='admin')
        save_model = models.Model.save
        for names, expected, base in (
            (('Concurrent & Category', 'Concurrent Category'), [201, 201], 'concurrent-category'),
            (('Duplicate Category', 'Duplicate Category'), [201, 400], 'duplicate-category'),
        ):
            barrier = Barrier(2, timeout=10)

            def save_at_barrier(instance, **kwargs):
                if isinstance(instance, Category) and instance.slug == base:
                    barrier.wait()
                return save_model(instance, **kwargs)

            def create(name):
                try:
                    client = APIClient()
                    client.force_authenticate(admin)
                    return client.post('/api/courses/categories/create/', {'name': name}, format='json').status_code
                finally:
                    connections.close_all()

            with patch.object(models.Model, 'save', save_at_barrier):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    self.assertEqual(sorted(pool.map(create, names)), expected)
        self.assertEqual(set(Category.objects.values_list('slug', flat=True)), {
            'concurrent-category', 'concurrent-category-1', 'duplicate-category',
        })
