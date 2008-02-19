"""
Test the various response formats.
"""

from shared import *

def test_common():
    """
    Common response stuff.
    """
    
    # Ensure that the http options are carried through to the actual response
    r = JsonResponse('data', http_status=404,
                    http_headers={'X-Custom': 'test'}).get_response()
    assert r.status_code == 404
    assert r['X-Custom'] == 'test'

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
    
    # check return mime type
    JsonResponse({}).get_response().mime_type = 'application/json'
    
    # test jsonp support
    assert JsonResponse([1, True], jsonp_callback='call').\
        get_response().content == 'call([1, true])'
    # an empty callback string is allowed too, and will still cause a
    # parenthesis  wrap
    assert JsonResponse([1, True], jsonp_callback='').\
        get_response().content == '([1, true])'