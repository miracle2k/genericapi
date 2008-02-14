from core import APIResponse, APIError

__all__ = (
    'PythonResponse', 'JsonResponse',
)

class PythonResponse(APIResponse):
    """
    Special response class that returns the native python objects, as
    retrieved from the user's API views. Exceptions are re-raised.
    """
    def get_response(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

class JsonResponse(APIResponse):
    """
    Serializes the response to JSON.
    Based on:
        http://www.djangosnippets.org/snippets/154/
    """
    def format(self, data):
        from django.db.models.query import QuerySet
        from django.utils import simplejson
        if data is None:
            content = ''
        elif isinstance(data, QuerySet):
            from django.core import serializers
            content = serializers.serialize('json', data)
        elif isinstance(data, APIError):
            content = simplejson.dumps(data.data)
        else:
            content = simplejson.dumps(data)
        return content
    def get_response(self, *args, **kwargs):
        response = super(JsonResponse, self).get_response(*args, **kwargs)
        response.mimetype='application/json'
        return response