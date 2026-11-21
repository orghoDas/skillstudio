import logging
from collections.abc import Mapping
from http import HTTPStatus

from django.core.exceptions import BadRequest, SuspiciousOperation, ValidationError as DjangoValidationError
from django.http import JsonResponse
from django.http.multipartparser import MultiPartParserError
from django.utils.log import log_response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler, set_rollback


logger = logging.getLogger(__name__)


def normalize_fields(fields):
    return {
        key: normalize_fields(value) if isinstance(value, Mapping) else [value] if isinstance(value, str) else value
        for key, value in fields.items()
    }


def api_error_payload(data, status_code):
    status = HTTPStatus(status_code)
    fallback_code = 'internal_error' if status_code == 500 else status.name.lower()
    fields = {}
    detail = 'An unexpected server error occurred.' if status_code == 500 else status.phrase
    code = fallback_code
    metadata = {}
    if isinstance(data, Mapping):
        reserved = {'detail', 'error', 'message', 'code', 'fields', 'errors', 'valid', 'revoked', 'revoked_at'}
        fields = {key: value for key, value in data.items() if key not in reserved}
        metadata = {key: data[key] for key in ('valid', 'revoked', 'revoked_at') if key in data}
        provided_fields = data.get('fields')
        if isinstance(provided_fields, Mapping):
            fields.update(provided_fields)
        if 'errors' in data:
            fields[api_settings.NON_FIELD_ERRORS_KEY] = data['errors']
        for key in ('detail', 'error', 'message'):
            value = data.get(key)
            if isinstance(value, str):
                detail = value
                code = getattr(value, 'code', fallback_code)
                break
            if value is not None:
                fields[key] = value
        returned_code = data.get('code')
        if isinstance(returned_code, str):
            code = returned_code
        elif returned_code is not None:
            fields['code'] = returned_code
    elif isinstance(data, list):
        fields[api_settings.NON_FIELD_ERRORS_KEY] = data
    if fields and status_code == 400 and code == fallback_code:
        code = 'validation_error'
        if detail == status.phrase:
            detail = 'Invalid input.'
    return {'detail': str(detail), 'code': str(code), 'fields': normalize_fields(fields), **metadata}


class APIErrorEnvelopeMiddleware:
    """Apply the same envelope to returned errors and raised exceptions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path_info.startswith('/api/') and response.status_code >= 400 and not isinstance(response, Response):
            headers = {k: v for k, v in response.headers.items() if k.lower() not in ('content-type', 'content-length')}
            normalized = JsonResponse(api_error_payload(None, response.status_code), status=response.status_code, headers=headers)
            normalized.cookies.update(response.cookies)
            return normalized
        return response

    def process_template_response(self, request, response):
        if request.path_info.startswith('/api/') and response.status_code >= 400 and isinstance(response, Response):
            response.data = api_error_payload(response.data, response.status_code)
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = 'application/json'
        return response


def handle_api_exception(exc, context):
    if isinstance(exc, DjangoValidationError):
        fields = (
            exc.message_dict if hasattr(exc, 'error_dict')
            else {api_settings.NON_FIELD_ERRORS_KEY: exc.messages}
        )
        messages = fields.get(api_settings.NON_FIELD_ERRORS_KEY, [])
        exc = ValidationError({
            'detail': messages[0] if messages else 'Invalid input.',
            'code': 'validation_error',
            'fields': fields,
        })
    elif isinstance(exc, ValidationError):
        fields = exc.detail if isinstance(exc.detail, Mapping) else {api_settings.NON_FIELD_ERRORS_KEY: exc.detail}
        messages = fields.get(api_settings.NON_FIELD_ERRORS_KEY, [])
        if isinstance(messages, str):
            detail = messages
        else:
            detail = messages[0] if isinstance(messages, list) and messages and isinstance(messages[0], str) else 'Invalid input.'
        exc = ValidationError({'detail': detail, 'code': 'validation_error', 'fields': fields})

    response = exception_handler(exc, context)
    if response is not None:
        return response

    # Let Django handle malformed requests and security exceptions, including
    # its logging of SuspiciousOperation.
    if isinstance(exc, (BadRequest, MultiPartParserError, SuspiciousOperation)):
        return None

    set_rollback()
    response = Response(
        {'detail': 'An unexpected server error occurred.', 'code': 'internal_error'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    log_response(
        'Unhandled API exception in %s',
        type(context.get('view')).__name__,
        response=response,
        request=context.get('request'),
        exception=exc,
        logger=logger,
    )
    return response
