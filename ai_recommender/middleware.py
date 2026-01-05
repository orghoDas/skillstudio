from django.http import HttpResponse
import logging


class IgnoreBrokenPipeMiddleware:
    """Middleware that catches BrokenPipeError / ConnectionResetError raised
    when the client disconnects while the server is writing the response.

    Instead of letting Django log a full traceback, this middleware logs a
    short debug message and returns an empty 204 response.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('django.request')

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except (BrokenPipeError, ConnectionResetError) as exc:
            # Client disconnected; log at debug to avoid noisy tracebacks
            try:
                self.logger.debug(
                    'Client disconnected: %s %s', request.path, exc,
                    exc_info=False,
                )
            except Exception:
                # Best-effort logging; do not raise
                pass
            # Return a minimal empty response; client already closed so this
            # will generally be ignored but keeps server logs quiet.
            return HttpResponse(status=204)
