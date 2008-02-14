"""
Test the various response formats.
"""

from shared import *
from genericapi.core import Dispatcher

class SampleAPI(GenericAPI):
    class Meta:
        expose_by_default = True
        def format_error(request, error):
            return {'error': True}

    def fail(request):
        raise APIError('you requested an error.')

def test_common():
    """
    Common response stuff.
    """

    # Try to create ``APIResponse`` classes with various data types and options
    APIResponse('')
    APIResponse({'count': 1})
    APIResponse({'count': 1}, http_status=200, http_headers={'custom': True})
    
    # If passed an exception, it's values are used
    e = APIError('message', code=9,
                 http_status=404,
                 http_headers={'Location': 'http://google.de'})
    r = APIResponse(e)
    assert r.data == e
    assert r.http_status == 404
    assert 'Location' in r.http_headers
    
    # If passed another ``APIResponse`` object, it's values are used
    r1 = APIResponse('data', http_status=404,
                    http_headers={'Location': 'http://google.de'})
    r2 = APIResponse(r1)
    assert r2.data == r1.data
    assert r2.http_status == 404
    assert 'Location' in r2.http_headers
    
    # Make sure we can always override the http meta data copied from an
    # ``APIResponse`` or ``APIError``. ``False`` works for removal.
    for data_obj in [r1, e]:
        r2 = APIResponse(data_obj, http_status=500, http_headers=False)
        assert r2.http_status == 500
        assert not r2.http_headers
    
def test_python_response():
    """
    Test raw python format.
    """
    def format(data): return PythonResponse(data).get_response()

    # everything is passed out unchanged
    assert format(5) == 5
    assert format('string') == 'string'
    assert format(True) == True
    assert format({}) == {}
    
    # even ``None``
    assert format(None) == None
    
    # errors (internal and all others) are raised / not catched
    raises(APIError, format, APIError())
    raises(TypeError, format, TypeError())

def test_json_response():
    """
    Test JSON response format.
    
    TODO: check queryset formatting (needs django setup with database?!)
    """
    def format(data): return JsonResponse(data).get_response().content

    # some basic datatypes
    assert format(5) == '5'
    assert format('string') == '"string"'
    assert format(True) == 'true'
    assert format({}) == '{}'

    # ``None`` should map to empty string
    assert format(None) == ''
    
    # check exception are formatted to valid json as well
    from django.utils import simplejson
    simplejson.loads(format(APIError('An error occured', code=2)))