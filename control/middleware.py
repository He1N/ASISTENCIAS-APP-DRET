from django.conf import settings
from django.shortcuts import render


class LimitesPlataformaMiddleware:
    """Evita descargas parciales o HTML truncado por el alojamiento."""
    def __init__(self, get_response):
        self.get_response = get_response

    def error(self, request):
        response = render(request, 'control/limite.html', status=413)
        response['Cache-Control'] = 'private, no-store'
        return response

    def __call__(self, request):
        limit = settings.HTTP_REQUEST_MAX_BYTES
        try:
            length = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            length = 0
        if limit and length > limit:
            return self.error(request)
        response = self.get_response(request)
        limit = settings.HTTP_RESPONSE_MAX_BYTES
        length = int(response.get('Content-Length', 0)) if response.streaming else len(response.content)
        if limit and length > limit:
            response.close()
            return self.error(request)
        return response
