from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.backends.base.operations import BaseDatabaseOperations
from rest_framework.generics import GenericAPIView
from rest_framework import serializers
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes


class SkillStudioAutoSchema(AutoSchema):
    """Keep explicit success schemas where views define serializers."""

    def _get_serializer(self):
        get_class = getattr(type(self.view), 'get_serializer_class', None)
        if not getattr(self.view, 'serializer_class', None) and get_class in (None, GenericAPIView.get_serializer_class):
            return OpenApiTypes.OBJECT
        return super()._get_serializer()

    def get_operation_id(self):
        path = self.path.strip('/').removeprefix('api/')
        parts = [segment.strip('{}').replace('-', '_') for segment in path.split('/')]
        return '_'.join([*parts, self.method.lower()])

    def _insert_field_validators(self, field, schema):
        super()._insert_field_validators(field, schema)
        if not isinstance(field, serializers.IntegerField) or not isinstance(field.parent, serializers.ModelSerializer):
            return
        if len(field.source_attrs) != 1:
            return
        try:
            model_field = field.parent.Meta.model._meta.get_field(field.source_attrs[0])
        except FieldDoesNotExist:
            return
        bounds = BaseDatabaseOperations.integer_field_ranges.get(model_field.get_internal_type())
        if bounds and ('maximum' in schema or 'minimum' in schema):
            lower, upper = bounds
            schema['minimum'] = max(schema.get('minimum', lower), lower)
            schema['maximum'] = min(schema.get('maximum', upper), upper)
            if lower >= -2**31 and upper <= 2**31 - 1 and schema.get('format') == 'int64':
                schema.pop('format')


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = 'accounts.authentication.CookieJWTAuthentication'
    name = ['bearerAuth', 'cookieAuth']

    def get_security_definition(self, auto_schema):
        return [
            {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'},
            {
                'type': 'apiKey', 'in': 'cookie', 'name': settings.JWT_AUTH_COOKIE,
                'description': 'Cookie-authenticated mutations also require the CSRF token.',
            },
        ]

    def get_security_requirement(self, auto_schema):
        return [{'bearerAuth': []}, {'cookieAuth': []}]


class APIKeyScheme(OpenApiAuthenticationExtension):
    target_class = 'accounts.authentication.APIKeyAuthentication'
    name = ['apiKeyHeader', 'apiKeyAuthorization']

    def get_security_definition(self, auto_schema):
        return [
            {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'},
            {'type': 'apiKey', 'in': 'header', 'name': 'Authorization', 'description': 'Use Api-Key <secret>.'},
        ]

    def get_security_requirement(self, auto_schema):
        return [{'apiKeyHeader': []}, {'apiKeyAuthorization': []}]


def add_error_contract(result, generator, request, public):
    schemas = result.setdefault('components', {}).setdefault('schemas', {})
    schemas['APIError'] = {
        'type': 'object',
        'required': ['detail', 'code', 'fields'],
        'properties': {
            'detail': {'type': 'string'},
            'code': {'type': 'string'},
            'fields': {'type': 'object', 'additionalProperties': True},
            'valid': {'type': 'boolean'},
            'revoked': {'type': 'boolean'},
            'revoked_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
        },
    }
    error = {
        'description': 'API error',
        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/APIError'}}},
    }
    for path in result['paths'].values():
        for operation in path.values():
            operation['responses'].setdefault('default', error)
    return result
