import logging

from django.core.exceptions import BadRequest, SuspiciousOperation, ValidationError as DjangoValidationError
from django.http.multipartparser import MultiPartParserError
from django.utils.log import log_response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler, set_rollback


logger = logging.getLogger(__name__)


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
