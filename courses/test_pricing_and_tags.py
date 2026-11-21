from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Course, Lesson, Module, Tag


class CoursePricingAndTagTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.instructor = User.objects.create_user(email='course-pricing@example.test', role='instructor')
        cls.course = Course.objects.create(title='Paid course', instructor=cls.instructor, price='20.00')
        cls.first_tag = Tag.objects.create(name='First tag')
        cls.second_tag = Tag.objects.create(name='Second tag')

    def setUp(self):
        self.client.force_authenticate(self.instructor)
        self.create = '/api/courses/create/'
        self.edit = f'/api/courses/{self.course.pk}/update/'

    def test_api_rejects_inconsistent_prices_and_accepts_inferred_creation_defaults(self):
        for is_free, price in ((False, '0.00'), (True, '2.00'), (False, '-1.00'), (True, '-1.00')):
            with self.subTest(is_free=is_free, price=price):
                response = self.client.post(self.create, {
                    'title': 'Rejected pricing', 'is_free': is_free, 'price': price,
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('price', response.data['fields'])
        self.assertFalse(Course.objects.filter(title='Rejected pricing').exists())

        for fields, expected in (({}, (True, '0.00')), ({'price': '3.75'}, (False, '3.75'))):
            response = self.client.post(self.create, {'title': 'Valid course', **fields}, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual((response.data['is_free'], response.data['price']), expected)

    def test_partial_updates_validate_against_the_existing_price_and_free_flag(self):
        self.assertEqual(self.client.patch(self.edit, {'price': '0'}, format='json').status_code, 400)
        turned_free = self.client.patch(self.edit, {'is_free': True}, format='json')
        self.assertEqual((turned_free.status_code, turned_free.data['is_free'], turned_free.data['price']), (200, True, '0.00'))
        self.assertEqual(self.client.patch(self.edit, {'is_free': False}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.edit, {'price': '30'}, format='json').status_code, 400)
        turned_paid = self.client.patch(self.edit, {'is_free': False, 'price': '30.00'}, format='json')
        self.assertEqual((turned_paid.status_code, turned_paid.data['is_free'], turned_paid.data['price']), (200, False, '30.00'))

    def test_db_rejects_invalid_pairs_through_queryset_updates(self):
        for fields in ({'price': 0}, {'is_free': True}, {'price': -1}):
            with self.subTest(fields=fields):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Course.objects.filter(pk=self.course.pk).update(**fields)
        self.course.is_free = True
        self.course.save(update_fields=['is_free'])
        self.course.refresh_from_db()
        self.assertEqual((self.course.is_free, self.course.price), (True, Decimal('0.00')))

    def test_tag_validation_preserves_existing_tags_and_course_review_on_failure(self):
        unknown = self.second_tag.pk + 1
        bad_create = self.client.post(self.create, {
            'title': 'Rejected tag', 'tag_ids': [self.first_tag.pk, unknown],
        }, format='json')
        self.assertEqual(bad_create.status_code, 400, bad_create.data)
        self.assertIn('tag_ids', bad_create.data['fields'])
        self.assertFalse(Course.objects.filter(title='Rejected tag').exists())

        duplicate_ids = [self.first_tag.pk, self.first_tag.pk, self.second_tag.pk]
        created = self.client.post(self.create, {'title': 'Tags on create', 'tag_ids': duplicate_ids}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(Course.objects.get(pk=created.data['id']).tags.count(), 2)

        self.course.tags.add(self.first_tag)
        module = Module.objects.create(course=self.course, title='Ready for review')
        Lesson.objects.create(module=module, title='Lesson')
        submitted = self.client.post(f'/api/courses/{self.course.pk}/submit/')
        self.assertEqual(submitted.status_code, 200, submitted.data)
        for bad_fields in ({'tag_ids': [unknown]}, {'price': '-1.00'}):
            invalid = self.client.patch(self.edit, {'title': 'Unsaved edit', **bad_fields}, format='json')
            self.assertEqual(invalid.status_code, 400, invalid.data)
        self.course.refresh_from_db()
        self.assertEqual((self.course.title, self.course.status), ('Paid course', 'under_review'))
        self.assertEqual(list(self.course.tags.all()), [self.first_tag])

        updated = self.client.patch(self.edit, {'tag_ids': duplicate_ids}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(set(self.course.tags.all()), {self.first_tag, self.second_tag})
        self.assertEqual(self.client.patch(self.edit, {'title': 'Omitted tags'}, format='json').status_code, 200)
        self.assertEqual(self.course.tags.count(), 2)
        self.assertEqual(self.client.patch(self.edit, {'tag_ids': []}, format='json').status_code, 200)
        self.assertFalse(self.course.tags.exists())


class PricingMigrationTests(TransactionTestCase):
    previous = [('courses', '0005_backfill_category_slugs')]
    target = [('courses', '0006_course_pricing_rules')]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_backfill_keeps_zero_cost_and_free_courses_free(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        apps = executor.loader.project_state(self.previous).apps
        user = apps.get_model('accounts', 'User').objects.create(email='pricing-migration@example.test')
        historical = apps.get_model('courses', 'Course').objects
        cases = (
            ('Zero-price paid', False, '0.00', True, '0.00'),
            ('Negative price', False, '-5.00', True, '0.00'),
            ('Mismatched free flag', True, '10.00', True, '0.00'),
            ('Valid paid course', False, '30.50', False, '30.50'),
        )
        for title, is_free, price, _, _ in cases:
            historical.create(title=title, slug=title.lower().replace(' ', '-'), instructor=user, is_free=is_free, price=price)
        MigrationExecutor(connection).migrate(self.target)
        for title, _, _, expected_free, expected_price in cases:
            course = Course.objects.get(title=title)
            self.assertEqual((course.is_free, course.price), (expected_free, Decimal(expected_price)))
