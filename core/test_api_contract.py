from pathlib import Path

import yaml
from django.conf import settings
from rest_framework.test import APITestCase

from accounts.models import User


class APIErrorContractTests(APITestCase):
    def test_router_errors_are_json_even_for_html_clients(self):
        error = self.client.get('/api/unknown-route/', HTTP_ACCEPT='text/html')
        self.assertEqual(error.status_code, 404)
        self.assertEqual(error.json(), {'detail': 'Not Found', 'code': 'not_found', 'fields': {}})

    def test_authentication_errors_keep_authenticate_headers(self):
        error = self.client.get('/api/accounts/me/', HTTP_ACCEPT='text/html')
        self.assertEqual(error.status_code, 401)
        self.assertIn('Bearer', error['WWW-Authenticate'])
        self.assertEqual(error.json()['code'], 'not_authenticated')
        self.assertEqual(error.json()['fields'], {})

    def test_direct_and_raised_validation_errors_share_an_envelope(self):
        student = User.objects.create_user(email='error-contract@example.test')
        self.client.force_authenticate(student)
        direct = self.client.post('/api/accounts/change-password/', {}, format='json')
        raised = self.client.post('/api/accounts/api-keys/', {}, format='json')
        coupon = self.client.post('/api/payments/coupons/validate/', {}, format='json')
        for error, field in ((direct, 'old_password'), (raised, 'label'), (coupon, 'code')):
            with self.subTest(field=field):
                self.assertEqual(error.status_code, 400)
                self.assertEqual(set(error.json()), {'detail', 'code', 'fields'})
                self.assertEqual(error.json()['code'], 'validation_error')
                self.assertIsInstance(error.json()['fields'][field], list)


    def test_malformed_filtered_queries_return_field_errors(self):
        admin = User.objects.create_user(email='filter-reviewer@example.test', role='admin')
        self.client.force_authenticate(admin)
        cases = (
            ('/api/payments/stats/', 'start_date'),
            ('/api/payments/instructor/earnings/', 'end_date'),
            ('/api/enrollments/', 'course'),
            ('/api/exams/questions/', 'course_id'),
            ('/api/students/notes/', 'lesson'),
            ('/api/students/notes/', 'course'),
        )
        for route, field in cases:
            with self.subTest(route=route, field=field):
                response = self.client.get(route, {field: 'garbage'})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()['fields'])
        self.assertEqual(self.client.get('/api/payments/stats/', {
            'start_date': '2026-11-01', 'end_date': '2026-11-02T00:00:00Z',
        }).status_code, 200)


class OpenAPIContractTests(APITestCase):
    def test_schema_endpoint_matches_snapshot_and_documents_core_contracts(self):
        response = self.client.get('/api/schema/', HTTP_ACCEPT='application/vnd.oai.openapi+json')
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        snapshot = Path(settings.BASE_DIR) / 'docs' / 'openapi.yaml'
        self.assertEqual(schema, yaml.safe_load(snapshot.read_text()))

        components = schema['components']
        self.assertEqual(set(components['schemas']['APIError']['required']), {'detail', 'code', 'fields'})
        self.assertEqual(
            set(components['securitySchemes']),
            {'bearerAuth', 'cookieAuth', 'apiKeyHeader', 'apiKeyAuthorization'},
        )
        paths = schema['paths']
        self.assertEqual(
            set(components['schemas']['PaginatedInstructorRosterEntryList']['properties']),
            {'count', 'next', 'previous', 'results', 'summary'},
        )
        self.assertIn('201', paths['/api/exams/{exam_id}/start/']['post']['responses'])
        for alias in ('/api/instructors/stats/', '/api/courses/instructor/dashboard/', '/api/enrollments/instructor/dashboard/'):
            self.assertNotIn(alias, paths)
            self.assertEqual(self.client.get(alias).status_code, 404)
