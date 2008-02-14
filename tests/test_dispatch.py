from urlparse import urlparse
from shared import *
from genericapi.core import Dispatcher
from django.http import HttpRequest, QueryDict

def make_request(url):
    r = HttpRequest()
    url = urlparse(url)
    r.GET = QueryDict(url.query)
    r.path = url.path
    return r

class SampleAPI(GenericAPI):
    class Meta: expose_by_default = True
    def noop(request): return None
    def give_me_true(request): return True
    def negate_bool(request, b): return not b
    def add(request, a, b): return a+b
    def make_list(request, *args): return list(args)
    def make_dict(request, **kwargs): return kwargs
    def echo(request, val): return val
    class ns(Namespace):
        def give_me_false(request): return False

def test_common():
    """
    Common dispatcher stuff.
    """
    request = make_request('/')
    # make sure using the base Dispatcher class fails properly
    raises(NotImplementedError, Dispatcher(SampleAPI), request)
    
    # [bug] excute debug dispatcher requires the ``request`` parameter to
    # be passed explicitely as a keyword; otherwise, we would have to use
    # type checking the first argument to determine whether or not a request
    # is meant to be included in the call.
    raises(BadRequestError, SampleAPI.execute, 'echo', 'not a request', 'text')

def test_json_dispatch():
    """
    Test JSON dispatcher.
    """
    # Note we are not using a response class. ``JSONResponse``
    # is tested separately.
    dispatcher = JsonDispatcher(SampleAPI, response_class=None)

    # simple, argument-less calls
    assert dispatcher(make_request('/give_me_true')) == True
    assert dispatcher(make_request('/ns/give_me_false')) == False
    # ``None`` should be a valid response
    assert dispatcher(make_request('/noop')) == None
    
    # invalid calls
    raises(MethodNotFoundError, "dispatcher(make_request('/give_me_5'))")

    # "special" positional argument
    assert dispatcher(make_request('/negate_bool/true')) == False
    assert dispatcher(make_request('/echo/[1,2,3,4]')) == [1,2,3,4]

    # keyword arguments
    assert dispatcher(make_request('/add/?a=1&b=2')) == 3
    assert dispatcher(make_request('/negate_bool/?b=false')) == True
    assert dispatcher(make_request('/add/?a=1&b=5')) == 6
    assert dispatcher(make_request('/make_dict/?a="b"&b="c"&c="a"')) == \
                                                {'a': 'b', 'b': 'c', 'c': 'a'}
    # invalid keyword arguments
    raises(BadRequestError, "dispatcher(make_request('/add/?a=1'))")
    raises(BadRequestError, "dispatcher(make_request('/add/?a=1&b=2&c=1'))")

    # mixed positional and keyword arguments
    assert dispatcher(make_request('/add/3?b=4')) == 7

    # check kwargs consistency
    # check GET kwargs and priority
    # TODO

    # previous tests already touch on this, but do it more thorough: check
    # various json type conversions.
    assert dispatcher(make_request('/echo/false')) == False
    assert dispatcher(make_request('/echo/true')) == True
    assert dispatcher(make_request('/echo/null')) == None
    assert dispatcher(make_request('/echo/"string"')) == "string"
    assert dispatcher(make_request('/echo/"str\\"ing"')) == "str\"ing"
    assert dispatcher(make_request('/echo/5')) == 5
    assert dispatcher(make_request('/echo/-1')) == -1
    assert dispatcher(make_request('/echo/[1,2,3,4]')) == [1,2,3,4]
    assert dispatcher(make_request('/echo/{"a": 1, "b": 2}')) == {'a': 1, 'b': 2}

def test_rest_dispatch():
    pass

def test_xmlrpc_dispatch():
    pass