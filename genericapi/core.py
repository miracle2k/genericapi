# encoding: utf-8

__all__ = (
    'expose', 'conceal', 'dispatcher', 'Namespace', 'GenericAPI'
)

# TODO: need alternative method (all public?) - document design decisions.
def expose(func):
    """
    Add this to each method that you want to expose via the API.

    Internally, it just adds an 'expose' attribute to the function, which will be
    picked up by DeclarativeHierarchyMetaclass. This should be considered an
    implementation detail - it is not recommended that you add the attribute
    manually.
    """
    func.expose = True
    return func
def conceal(func):
    pass
def dispatcher(*args):
    """
    Make this method or namespace only public via certain dispatchers.
    @dispatcher('json', 'rest')
    def apimethod(x): pass
    """
    pass

NAMESPACE_SEPERATOR = '.'

def mkns(namespace, add):
    result = namespace
    if namespace and add: result += NAMESPACE_SEPERATOR
    result += add
    return result.lower()

class DeclarativeHierarchyMetaclass(type):
    """
    Metaclass that converts Field attributes to a dictionary called
    'base_fields', taking into account parent class 'base_fields' as well.
    """
    def __new__(cls, name, bases, attrs):
        # first, create an instance...
        methods = {}
        for base in bases:
            methods.update(getattr(base, 'methods', {}))
        attrs.update({'methods': methods})

        inst = type.__new__(cls, name, bases, attrs)
        # ...then modify.
        inst.add_namespace(attrs.items())
        return inst

    def add_namespace(cls, namespace, name=''):
        """
        Looks for API methods in the class specified by 'namespace',
        and adds them to the method registration.

        'namespace' really can be of any type, although Namespace or a
        subclass are  recommended. It can also be any iterable that returns
        tuples in the form of (fieldname, object).

        'name' is the name to use for the namespace. If no name is specified,
        the methods will be added at a root level.

        Note that while/because this is defined in the metaclass, you'll be able
        to call it on your API class, e.g.
            def MyAPI(GenericAPI); MyAPI.add_namespace()
        """
        # if there is a __dict__, use it, otherwise assume an iterable.
        if hasattr(namespace, '__dict__'): iterable = namespace.__dict__.items()
        else: iterable = namespace

        for field_name, field_obj in iterable:
            # inner namespace class: recursively find all it's methods - use
            # this field's name as the sub-namespace.
            if isinstance(field_obj, type) and issubclass(field_obj, Namespace):
                cls.add_namespace(field_obj, mkns(name, field_name))
            # an api method: add at the current namespace level
            elif hasattr(field_obj, 'expose'):
                cls.add_method(field_obj, mkns(name, field_name))

    def add_method(cls, method, name):
        """
        Adds the specified method to the APIs method registry. The name given
        must be fully-qualified (i.e. include the namespace path). You can
        use the mkns() function to build one.

        Note that while/because this is defined in the metaclass, you'll be able
        to call it on your API class, e.g.
            def MyAPI(GenericAPI); MyAPI.add_method()
        """
        cls.methods.update({name: method})

class Namespace(object):
    """
    Just used to identify the inner classes we care about. This also
    allows the user of non-namespaces inner classes, as opposed to making
    every inner class a namespace by default.
    """
    pass

class GenericAPI(object):
    """
    Baseclass for an API. It's metaclass will look for:

        * every method declared in this class decorated with @expose
        * every inner class subclassing Namespace, recursively
        * each @expose-decorated method in each of those inner Namespace classes

    It will then make all those methods available as classmethods in a
    flat dict called 'methods', which might look like this:

    methods = {
        'genericapi.method1': method1,
        'genericapi.namespace.method2': method2,
        'genericapi.namespace.namespace.anothermethod': anothermethod,
        'genericapi.users.get': get,
        'genericapi.groups.get': get,
        ...
    }

    Additional notes:

        * The original methods and Namespace classes are retained.
        * Subclassing is supported. API methods from base classes are availabe
          as well.
        * Subclassing of Namespace is currently *not* supported. API methods
          in base classes will be ignored.
    """

    __metaclass__ = DeclarativeHierarchyMetaclass

    # leave instantiation out of the picture for now, to keep things less complex
    def __new__(*args, **kwargs):
        raise Exception('You can not create instances of API classes.')

    @classmethod
    def execute(cls, methodname, *args, **kwargs):
        """
        """
        if not methodname in cls.methods:
            raise Exception('%s is not a valid method name' % methodname)
        return cls.methods[methodname](*args, **kwargs)

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
        method = get_method_name(url)
        try:
            if method.needs_key:
                if not self._api.check_key():
                    raise KeyInvalid()
            if method.needs_auth:
                if not self._api.check_auth():
                    raise AuthInvalid()

            params = self.parse_request(request)
            result = self._api.execute(method, params)
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