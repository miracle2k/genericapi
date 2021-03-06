from urlparse import urlparse
from shared import *
from genericapi.core import Dispatcher
from django.http import HttpRequest, QueryDict

def make_request(url, method=None, post=None):
    r = HttpRequest()
    url = urlparse(url)
    r.GET = QueryDict(url[4])  # url.query (2.5)
    r.path = url[2]            # url.path (2.5)
    if method: r.method = method
    if post: r.POST.update(post)
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
        def with_param(request, param): return param
    class rest(Namespace):
        class resource(Namespace):
            def get(request, id): return True
            def delete(request, id): return True
            def post(request, payload): return True
            def put(request, id, payload): return True

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
    
    # [bug] check handling of the "response_class" argument; ``False`` disables
    # it, and ``None`` (or argument missing) falls back to the default, if any.
    assert JsonDispatcher(None, response_class=False).response_class == False
    assert Dispatcher(None, response_class=None).response_class is None
    assert JsonDispatcher(None, response_class=None).response_class is not None
    assert JsonDispatcher(None).response_class is not None

def test_json_dispatch():
    """
    Test JSON dispatcher.
    """
    # Note we are not using a response class. ``JSONResponse``
    # is tested separately.
    dispatcher = JsonDispatcher(SampleAPI, response_class=False)

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
    # [bug] make sure positional as well as keyword arguments work sublevels
    assert dispatcher(make_request('/ns/with_param/5')) == 5
    assert dispatcher(make_request('/ns/with_param/?param=5')) == 5
    # invalid keyword arguments
    raises(BadRequestError, "dispatcher(make_request('/add/?a=1'))")
    raises(BadRequestError, "dispatcher(make_request('/add/?a=1&b=2&c=1'))")
    
    # [bug] invalid json raises a BadRequestError (and not say, a ValueError)
    raises(BadRequestError, "dispatcher(make_request('/negate_bool/?d={['))")
    # the JSON value that failed is accessible via an attribute
    try: dispatcher(make_request('/negate_bool/?d={['))
    except Exception, e: assert isinstance(e.value, basestring)
    
    # mixed positional and keyword arguments
    assert dispatcher(make_request('/add/3?b=4')) == 7

    # check kwargs consistency
    # check GET kwargs and priority
    # TODO

    # previous tests already touch on this, but do it more thorough: check
    # various json type conversions
    assert dispatcher(make_request('/echo/false')) == False
    assert dispatcher(make_request('/echo/true')) == True
    assert dispatcher(make_request('/echo/null')) == None
    assert dispatcher(make_request('/echo/"string"')) == "string"
    assert dispatcher(make_request('/echo/"str\\"ing"')) == "str\"ing"
    assert dispatcher(make_request('/echo/5')) == 5
    assert dispatcher(make_request('/echo/-1')) == -1
    assert dispatcher(make_request('/echo/[1,2,3,4]')) == [1,2,3,4]
    assert dispatcher(make_request('/echo/{"a": 1, "b": 2}')) == {'a': 1, 'b': 2}
    
    # test jQuery compat mode: no special handling of '_' in standard mode
    raises(BadRequestError, "dispatcher(make_request('/noop/?_=123'))")
    dispatcher = JsonDispatcher(SampleAPI, jquery_compat=True, response_class=False)
    # in compat mode, '_' is ignored (used by jQuery to force disable caching
    # by passing a timestamp)
    dispatcher(make_request('/noop/?_=123'))
    
    # test jsonp callbacks:
    # 1) they are enabled by default
    dispatcher(make_request('/noop/?jsonp=cb'))
    # 2) they are passed along correctly to the response
    dispatcher = JsonDispatcher(SampleAPI)
    assert dispatcher(make_request('/noop/?jsonp=cb')).content == 'cb()'
    # 3) custom argument name
    dispatcher = JsonDispatcher(SampleAPI, jsonp_callback='mycb', response_class=False)
    dispatcher(make_request('/noop/?mycb=cb'))
    # 4) they can be disabled
    dispatcher = JsonDispatcher(SampleAPI, jsonp_callback=False, response_class=False)
    raises(BadRequestError, "dispatcher(make_request('/noop/?jsonp=cb'))")
    
    

def test_rest_dispatch():
    """
    Test rest dispatcher.
    """
    # note that we are not using a response class
    dispatcher = RestDispatcher(SampleAPI, response_class=False)
    
    # test the various http methods
    assert dispatcher(make_request('/rest/resource/1', 'GET')) == True
    assert dispatcher(make_request('/rest/resource/1', 'DELETE')) == True
    assert dispatcher(make_request('/rest/resource/1', 'PUT', {'v': 1})) == True
    assert dispatcher(make_request('/rest/resource/', 'POST', {'v': 1})) == True

def test_xmlrpc_dispatch():
    pass
