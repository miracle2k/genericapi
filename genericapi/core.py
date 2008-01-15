# encoding: utf-8
import types

__all__ = (
    'expose', 'conceal', 'dispatcher', 'Namespace', 'GenericAPI',
    'JsonDispatcher'
)

# TODO: need alternative method (all public?) - document design decisions.
def expose(func):
    """
    Add this to each method that you want to expose via the API.

    Internally, it just adds an attribute to the function object, indicating
    it's exposed status. This should be considered an implementation detail -
    it is not recommended that you add the attribute manually.
    """
    func.exposed = True
    return func
def conceal(func):
    """
    The counterpart of 'expose' - explicitly hides a method from the API.
    """
    func.concealed = True
    return func

def dispatcher(*args):
    """
    Make this method or namespace only public via certain dispatchers.
    @dispatcher('json', 'rest')
    def apimethod(x): pass
    """
    pass

class MakeAllMethodsStatic(type):
    """
    Metaclass that convert makes all methods of a class static.
    """
    def __new__(cls, name, bases, attrs):
        for a in attrs:
            if (isinstance(attrs[a], types.FunctionType) and not a in ['__new__']):
                attrs[a] = staticmethod(attrs[a])
        return type.__new__(cls, name, bases, attrs)

class Namespace(object):
    """
    Just used to identify the inner classes we care about. This allows the use
    of non-namespaces inner classes, as opposed to making every inner class a
    namespace by default. Being explicit about this also reduces the change
    of accidentally making methods accessible that are intended to be private.
    """
    __metaclass__ = MakeAllMethodsStatic

class GenericAPI(Namespace):
    """
    Baseclass for an API.
    
    class MyAPI(GenericAPI):
        @expose
        def echo(request, text): return text
        
        class comments(Namespace):
            @expose
            def add(request, text): pass
            
    Things to note:
        * Decorate methods that you want to make available with @expose.
        * All methods in the class and all namespaces are static by default.
        
    If can expose methods by default, and hide on request:
    
    class MyAPI(GenericAPI):
        expose_by_default = True
        def echo(request, text): return text
        @conceal
        def private(): pass
        
    Use a dispatcher to make an API available via your urlconf.
    """
    def __new__(*args, **kwargs):
        raise TypeError('API classes cannot be instantiated.')
    
    @classmethod
    def resolve(self, path):
        """
        Returns the method specified in the list (or tuple) in path, or None.
        At this point, we do not yet check if the method is actually exposed.
        """
        obj = self
        for name in path:
            # TODO: support base classes! handle private attributes correctly!
            obj = obj.__dict__.get(name)
            if obj is None: return None
        # Note that we return the function object, not the staticmethod. We can
        # also just pass "None" instead of the actual namespace object the
        # method is possibly defined on, because Python's staticmethod()
        # doesn't need it anyway.
        if isinstance(obj, staticmethod):
            return obj.__get__(obj, None)
        else:
            return None

    @classmethod
    def execute(self, method, *args, **kwargs):
        """
        Executes an exposed method with the given arguments. You can specify
        the method either as a dotted string ("comments.add"), or as a function
        type. If the method does not exist or is not exposed, an AttributeError
        will be raised.
        """
        if isinstance(method, str):
            method = self.resolve(method.split('.'))
            if method is None: raise AttributeError()
        
        if not (getattr(method, 'exposed', False) or \
                    (getattr(self, 'expose_by_default', False) and
                     not getattr(method, 'concealed', False))):
            raise AttributeError()
        
        method(*args, **kwargs)

class APIResponse(object):
    pass

class JsonResponse(APIResponse):
    pass

class XmlRpcResponse(APIResponse):
    pass

class Dispatcher(object):
    """
    Dispatcher base class. Dispatchers are responsible for resolving an
    incoming request into an API method call. Use them to hook your API into
    your urlpatterns:

    urlpatterns = patterns('',
        (r'^api/json/(.*)$',  JsonDispatcher(MyAPI)),
        (r'^api/xmlrpc/(.*)$',  XmlRpcDispatcher(MyAPI)),
    )

    Each dispatcher returns the API response in an appriopriate default format,
    but if you want to, you can let your XmlRpc API return Json:

    urlpatterns = patterns('',
        (r'^api/xmlrpc/(.*)$',
                XmlRpcDispatcher(MyAPI, response_class=JsonResponse)),
    )
    """

    # TODO: param: allow header auth
    def __init__(self, api, response_class=None):
        self.api = api
        self.response_class = response_class or self.default_response_class

    def __call__(*args, **kwargs):
        dispatch(*args, **kwargs)

    def dispatch(self, request, url):
        """
        Resolves an incoming request to an API call, calls the method, and
        returns it's result, converted via the response_class attribute, as a
        Django Response object.
        # TODO: let the API class define error() handler methods
        """
        method, args, kwargs = self.parse_request(request, url)
        try:
            #if method.needs_key:
            #    if not self._api.check_key():
            #        raise KeyInvalid()
            #if method.needs_auth:
            #    if not self._api.check_auth():
            #        raise AuthInvalid()
            result = self.api.execute(method, args, kwargs)
            return result
        except:
            # return error resposne
             #<response>
             #   <status>failed</status>
             #   <error>A valid api_key is required to access this URL.</error>
             #  </response>
            pass
        else:
            # return response
            return self.response_class(result)

class JsonDispatcher(Dispatcher):
    """
    Uses '/' as a namespace separator, a comma ',' for separating parameters,
    and expects parameters to be Json encoded. Ignores any POST payload.

    GET /test
    ==> api.test()

    GET /test/x=200,y=["a","b","c"]
    ==> api.test(x=200, y=["a","b","c"])

    String parameters do not necessarily need to be quoted, with the exception
    of "true", "false", and "null":

    GET /echo/"hello",world,"null"
    ==> api.echo("hello", "world", "null")

    GET /comments/add/great post!,author=null
    ==> api.comments.add("great post!", author=None)
    """

    default_response_class = JsonResponse

    def parse_url(self, request):
        pass

class RestDispatcher(Dispatcher):
    """
    Works like the JsonDispatcher with respect to arguments, but tries to
    push you towards restful api design by appending the HTTP method used to
    the method path.
    # TODO: what about http status code returns
    # TODO: different payload parsers (xml, json, ...)

    GET /comments/1
    ==> api.comments.get(1)

    DELETE /comments/1
    ==> api.comments.delete(1)

    PUT /comments/1
    {sdfsdf}
    ==> api.comments.put(1,payload=[])

    POST /comments/
    {sdfsdf}
    ==> api.comments.post(payload=[])

    Additional arguments can be used as well:

    GET /comments/1,full=true
    POST /comments/mark_as_spam=true

    If you want to provide your API both in REST and other formats, check out
    the @verb decorator.
    """

    default_response_class = JsonResponse

    def parse_url(self, request):
        pass

class XmlRpcDispatcher(Dispatcher):
    """
    Accepts the regular XML-RPC method call via POST. Fails on GET, or if
    called with a (sub-)url. Uses a dot  "." for separating namespaces.

    POST /
    <?xml version="1.0"?>
    <methodCall>
      <methodName>comments.add</methodName>
      <params>
        <param><value><string>great post!</string></value></param>
      </params>
    </methodCall>
    ==> api.comments.add("great post!")

    Note that keyword arguments are not supported.
    """

    default_response_class = XmlRpcResponse

    def parse_url(self, request):
        pass