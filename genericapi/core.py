# encoding: utf-8
import types, re

# TODO: implement signature enforcing
# TODO: support namespaces that "consume" an element of the path

__all__ = (
    'expose', 'conceal', 'Namespace', 'GenericAPI',
    'JsonDispatcher',
    'BadRequestError', 'MethodNotFoundError',
)

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
    func.exposed = False
    return func

class APIError(Exception):
    # => similar constructor as APIResponse
    message = None
    code = None
    http_status = None
    http_headers = {}
class BadRequestError(APIError): pass
class MethodNotFoundError(APIError): pass

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
        * Subclassing is supported for the API as well as single namespaces.

    If can expose methods by default, and hide on request:

    class MyAPI(GenericAPI):
        expose_by_default = True
        def echo(request, text): return text
        @conceal
        def private(): pass

    In subclassing is used, expose_by_default only applies to the class it is
    defined in. It does not change the behaviour of super or child classes.
    exposes_by_default also works on Namespaces.

    Use a dispatcher to make an API available via your urlconf.
    """
    def __new__(*args, **kwargs):
        raise TypeError('API classes cannot be instantiated.')

    @classmethod
    def resolve(self, path):
        """
        Returns the exposed method specified in the list (or tuple) in path, or
        None if the path could not be resolved, or the method targeted is not
        exposed.
        """
        def _find(obj, index=0, parent_default_expose=None):
            name = path[index]

            # only look in namespaces
            if not (isinstance(obj, type) and issubclass(obj, Namespace)):
                return None
            # try to detect private members, which we never let access
            if name.startswith('_%s__'%obj.__name__): return None

            # look for the current part of the path in the passed object and
            # all it's super classes, recursively.
            for obj in obj.__mro__:
                if name in obj.__dict__:
                    # expose_by_default is a bit though. We don't want it to
                    # work though classic inheritance (i.e. each class has it's
                    # own value), but namespaces should inherit the value from
                    # their parents. so we drag the value from the current
                    # object with us while handling the childs, and use it
                    # when an object does not define the attribute itself.
                    expose_by_default = \
                        getattr(obj, 'expose_by_default', parent_default_expose)

                    # if we don't have resolved the complete path yet, continue
                    if index < len(path)-1:
                        attr = _find(obj.__dict__[name], index+1, expose_by_default)
                        # if we found something, return it, otherwise continue
                        if attr: return attr

                    # otherwise, check that what we have arrived it is valid,
                    # callable etc., and then return it. otherwise just
                    # continue the search.
                    else:
                        attr = obj.__dict__[name]
                        # Try to resolve the staticmethod into a function via
                        # the descriptor protocol..
                        if isinstance(attr, staticmethod):
                            method =  attr.__get__(obj)
                            # check accessibility
                            if getattr(method, 'exposed', expose_by_default):
                                return method
            # backtrack
            return None

        # from the root namespace (self), traverse the class hierarchy
        return _find(self)

    @classmethod
    def execute(self, method, *args, **kwargs):
        """
        Mini-dispatcher that executes a method by it's name specified in
        dotted notation.
        """
        method = self.resolve(method.split('.'))
        if method is None: raise AttributeError()
        else: return method(*args, **kwargs)

from django.http import HttpResponse

class APIResponse(object):
    """
    Use can return this in your api funcs for additional options
    return APIResponse(data, status=200, headers={})
    => similar constructor as APIError
    """
    @classmethod
    def make(self, data):
        # if the data is an exception, we need to format it into a data object,
        # while still preserving http status etc too => response object
        if data is APIError:
            data = data.to_response(data=self.format_error(data))

        if data is APIResponse:
            content = get_response(data.data)
        else:
            content = get_response(data)

        return HttpResponse(content=content)

class JsonResponse(APIResponse):
    def get_response(self, data):
        return HttpResponse()

class XmlRpcResponse(APIResponse):
    def get_response(self, data):
        if isinstance(data, APIError):
            # convert to fault xmlrpc message
            pass
        else:
            # convert standard
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

    default_response_class = None

    # TODO: param: allow header auth
    def __init__(self, api, response_class=None):
        self.api = api
        self.response_class = response_class or self.default_response_class

    def __call__(self, *args, **kwargs):
        return self.dispatch(*args, **kwargs)

    def format_error(self, error):
        """
        Convert the exception in error into a data object. as there is no "one
        way" to do this, we let the user handle it via a special function
        defined in the API class. The base class provides a default
        implementation, so this is optional.
        """
        pass

    def parse_request(self, request, url):
        """
        Override this when implementing a dispatcher. Must return a 3-tuple(!)
        of (path, args, kwargs), with path being a list or tuple pointing
        to the requested method (see also GenericAPI.resolve).

        The function can also return a list(!) of such 3-tuples if a unique
        call cannot be determined. However, make sure the variants are always
        exclusive. A situation where a wrong method could accidentally be must
        not arise.

        Should a problem occur that prevents from returning a meaningful result,
        raise a BadRequestError.
        """
        raise NotImplementedError()
    del parse_request

    def dispatch(self, request, url=None):
        """
        Resolves an incoming request to an API call, calls the method, and
        returns it's result, converted via the response_class attribute, as a
        Django Response object.

        request is a Django Request object. url is the sub-url of the
        request to be resolved. If it is missing, request.path is used.
        """
        if not hasattr(self, 'parse_request'):
            raise NotImplementedError()

        try:
            # TODO: let the API class define error() handler methods
            resolved = self.parse_request(request, url or request.path)
            if isinstance(resolved, tuple): resolved = [resolved]

            # try to resolve to a method call
            method = None
            for path, args, kwargs in resolved:
                method = self.api.resolve(path)
                if method: break;
            if method is None:
                raise MethodNotFoundError()

            # call the first method found
            #if method.needs_key:
            #    if not self._api.check_key():
            #        raise KeyInvalid()
            #if method.needs_auth:
            #    if not self._api.check_auth():
            #        raise AuthInvalid()
            # raises TypeError
            result = method(request, *args, **kwargs)
        # Catch our own errors only. everything else will bubble up to Django's
        # exception handling. If you don't want that, you can always handle
        # them in your custom dispatcher.
        except APIError, e:
            result = e

        if not self.response_class:
            # raise exception or return unmodified, or .data in APIResponse case
            pass
        else:
            return self.response_class().get_response(result)

class JsonDispatcher(Dispatcher):
    """
    Reads the method name from the URL, using '/' as a namespace separator.
    Arguments are passed via the querystring, and as such, only keyword
    arguments are supported. The exception is one (!) positional argument that
    can be appended to the url. All arguments are expected to be formatted in
    json. Ignores any POST payload.

    GET /test
    ==> api.test()

    GET /echo/["hello world"]
    ==> api.test(["hello world"])

    GET /comments/add/"great post"/?moderation=true&author=null
    ==> api.comments.add("great post!", moderation=True, author=None)
    """
    default_response_class = JsonResponse
    # TODO: allow simple strings option
    # TODO: allow GET params option

    ident_regex = re.compile('^[_a-zA-Z][_a-zA-Z0-9]*$')

    def __parse(self, request, path, argstr):
        from django.utils import simplejson

        # convert the positional argument from json to python
        if argstr:
            try: args = [simplejson.loads(argstr)]
            except ValueError, e: raise BadRequestError(e)
        else:
            args = []

        # convert json query strings into kwargs array
        kwargs = {}
        for key, value in request.GET.items():
            kwargs[str(key)] = simplejson.loads(value)
        return path, args, kwargs

    def parse_request(self, request, url):
        # Split the path and remove empty items
        path = filter(None, url.split('/'))
        if path:
            # Unless their are at least two items in path, there can not be any
            # arguments at all.
            if len(path) < 2:
                return self.__parse(request, path, '')
            # If the last item is not an identifier, it must either be the
            # argument portion, or an invalid call. We just assume the former.
            # Note that there is no danger for the wrong function being
            # accidently called because of this, as the previous identier in
            # the path would have to be a namespace, and the call would fail
            # anyway (albeit due to a different reason).
            #
            #   /namespace/call,  (=> accidental ",", considered an argument)
            #   => error would be"namespace cannot be called" instead of
            #      "namespace.call does not exist".
            elif not self.ident_regex.match(path[-1]):
                return self.__parse(request, path[:-1], path[-1])
            # Otherwise, we can't say for sure if the last part is an attribute
            # or not, so we try to return both options. This is ok for the same
            # reasons outlined above: it cannot lead to the wrong call.
            else:
                # if an error is raised at this point for the argument option,
                # then we already know it can't work out, and leave it off.
                try: option1 = self.__parse(request, path[:-1], path[-1])
                except BadRequestError: option1 = None
                return (option1 and [option1] or []) + [(path, [], {})]

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