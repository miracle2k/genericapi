# encoding: utf-8
import types, re
from django.http import HttpResponse

# TODO: implement signature enforcing (includes types, "int" etc).
# TODO: support namespaces that "consume" an element of the path
# TODO: support JSONP callbacks
# TODO: support per_method dispatching: api views are hooked manually into
# urlconf, the dispatcher only resolves parameters.

__all__ = (
    'expose', 'conceal', 'check_key', 'process_call',
    'Namespace', 'GenericAPI', 'Dispatcher', 'APIResponse',
    'APIError', 'BadRequestError', 'MethodNotFoundError', 'InvalidKeyError',
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

def check_key(check_key_func):
    """
    Allows to specificy custom api key validation on a per-method level:
    
    @expose
    @check_key(lambda request, key: key == 'topsecret')
    def add(request): return True
    
    Passing ``False`` for the validation function disables the key requirement
    for this method.
    
    Internally, it just adds an attribute to the function object.
    """
    def decorator(apply_to_func):
        apply_to_func.check_key = check_key_func
        return apply_to_func
    return decorator

def process_call(process_call_func):
    """
    Allows to specificy custom process_call handlers on a per-method level:

    @expose
    @process_call(require_login_session)
    def add(request): return True

    Passing ``False`` for the validation function disables the key requirement
    for this method.

    Internally, it just adds an attribute to the function object.
    """
    def decorator(apply_to_func):
        apply_to_func.process_call = process_call_func
        return apply_to_func
    return decorator

class APIError(Exception):
    """
    Base class for all API-related exceptions. Raising ``APIError``s in your
    views is the recommended way to handle errors - dispatchers usually convert
    them into an error response in the appropriate format.
    
    ``__init__`` takes the the optional arguments ``message`` and ``code``,
    which hold details about the error occured, as well as ``http_status`` and
    ``http_headers`` that are used when the error is converted to a HTTP
    response.

    See also ``APIResponse``, which has a similar interface.

    Views can also return Exception instances instead of raising them.
    """
    def __init__(self, message="", code=None, http_status=None, http_headers=None):
        self.message, self.code = message, code
        self.http_status, self.http_headers = http_status, http_headers
        
    def _get_data(self):
        """
        Provides the default formatting for exceptions; Unless overriden by the
        user, this function determines how an exception is serialized.
        """
        value = self.__dict__.get('data', None)
        if value is None:
            value = {'error': self.message or True}
            if self.code: value['code'] = self.code
        return value
    def _set_data(self, value):
        self.__dict__['data'] = value
    data = property(_get_data, _set_data)
    
class MethodNotFoundError(APIError): pass
class InvalidKeyError(APIError): pass
class BadRequestError(APIError): pass

class apimethod(object):
    """
    We frequently assign attributes to api views, which ``staticmethod`` makes
    very hard, as it's readonly. Using our own version instead makes everything
    much less complex (otherwise, we'd attach the attributes to to the function
    object itself, which we have to retrieve via the descriptor protocol
    (__get__) everytime we need access).
    """
    def __init__(self, func):
        self.func = func
    def __call__(self, *args, **kwargs):
      return self.func(*args, **kwargs)
    def __getattr__(self, name):
        """
        Fall back to function object itself. Attributes set via decorators are
        usually found there.
        """
        return getattr(self.func, name)

class NamespaceOptions(object):
    """
    Holds the options defined in a ``Meta`` subclass.
    """
    def __init__(self, options=None):
        self.parent = None
        self.expose_by_default = getattr(options, 'expose_by_default', None)
        self.key_header = getattr(options, 'key_header', None)
        self.key_argument = getattr(options, 'key_argument', None)
        check_key = getattr(options, 'check_key', None)
        self.check_key = check_key and check_key.im_func or check_key
        process_call = getattr(options, 'process_call', None)
        self.process_call = process_call and process_call.im_func or process_call
        format_error = getattr(options, 'format_error', None)
        self.format_error = format_error and format_error.im_func or format_error
    def __getattribute__(self, attr):
        """
        If a value is ``None``, automatically fall back to the parent
        namespace's options.
        """
        val = super(NamespaceOptions, self).__getattribute__(attr)
        parent = super(NamespaceOptions, self).__getattribute__('parent')
        if val is None and parent:
            return getattr(parent, attr)
        return val

class Namespace(object):
    """
    Forward define an identifer called ``Namespace``. This is necessary because
    we need to reference ``Namespace`` within it's own metaclass. For child
    classes the user defines this is no problem, but for the base ``Namespace``
    class itself the metaclass code runs as well (before the class is defined).

    Of course, this and the real ``Namespace`` class are different, but that's
    ok: The code in question wouldn't have any effect for the base
    ``Namespace`` class anyway.
    """
    pass

class NamespaceMetaclass(type):
    """
    Makes all methods of the class static, converts the ``Meta`` subclass
    to a NamespaceOptions instance, and some other things.
    """
    def __new__(cls, name, bases, attrs):
        opts = NamespaceOptions(attrs.pop('Meta', None))
        attrs['_meta'] = opts
        
        # convert all functions to static ``apimethod``s.
        for a in attrs:
            if isinstance(attrs[a], types.FunctionType) and not a in ['__new__']:
                attrs[a] = apimethod(attrs[a])

        # create the namespace
        self = type.__new__(cls, name, bases, attrs)
    
        # pre-process: add references to this newly created namespaces to all
        # sub-namespaces and methods.
        for a in attrs:
            attr = getattr(self, a)
            if isinstance(attr, apimethod):
                attr._namespace = self
            # this is the code that requires the ``Namespace`` forward decl
            elif isinstance(attr, type) and issubclass(attr, Namespace):
                attr._meta.parent = self._meta
                
        return self

class Namespace(object):
    from django.newforms import ModelForm
    """
    Just used to identify the inner classes we care about. This allows the use
    of non-namespaces inner classes, as opposed to making every inner class a
    namespace by default. Being explicit about this also reduces the change
    of accidentally making methods accessible that are intended to be private.
    """
    __metaclass__ = NamespaceMetaclass

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
        * Decorate methods that you want to make available with ``@expose``.
        * All methods in the class and all namespaces are static by default.
        * Subclassing is supported for the API as well as single namespaces.

    If can expose methods by default, and hide on request:

    class MyAPI(GenericAPI):
        class Meta:
            expose_by_default = True
        def echo(request, text): return text
        @conceal
        def private(): pass

    If subclassing is used, ``expose_by_default`` only applies to the class it
    is defined in. It does not change the behaviour of super or child classes.
    ``exposes_by_default`` also works on namespaces.

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
        def _find(obj, index=0):
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
                    # if we don't have resolved the complete path yet, continue
                    if index < len(path)-1:
                        attr = _find(obj.__dict__[name], index+1)
                        # if we found something, return it, otherwise continue
                        if attr: return attr

                    # otherwise, check that what we have arrived it is valid,
                    # callable etc., and then return it. otherwise just
                    # continue the search.
                    else:
                        method = obj.__dict__[name]
                        if isinstance(method, apimethod):
                            if getattr(method, 'exposed', obj._meta.expose_by_default):
                                return method
            # backtrack
            return None

        # from the root namespace (self), traverse the class hierarchy
        return _find(self)

    @classmethod
    def execute(self, method, *args, **kwargs):
        """
        Mini-dispatcher that executes a method by it's name specified in
        dotted notation. If ``request`` is not passed in, ``None`` is used
        automatically, but this might break your views, of course.
        """
        response_class = kwargs.pop('response_class', None)
        request = kwargs.pop('request', None)
        from dispatch import SimpleDispatcher
        return SimpleDispatcher(self, response_class).dispatch(
            method, request, *args, **kwargs)
            
class APIResponse(object):
    """
    An "API response" is used by the depatcher to format to output. Child
    classes can implement formats like JSON or XML by implementing the
    ``format`` method.

    API views can choose to return an instance of this class instead of
    raw data, in order to pass along metadata like a status code or or
    additional headers. For example, a REST api might want to return a HTTP
    ``Location`` header for a newly posted resource:

    def post(request, name):
        # ...
        return APIResponse(None,
            headers={'Location': reverse(view, args=[new_id])}

    See also ``APIError``, which has a partly similar interface.
    """
    # TODO: rename to ``Response``?
    def __init__(self, data, http_status=None, http_headers=None):
        # If another response object is passed, clone it; this allows the
        # dispatcher code to handle ``APIResponse`` objects from a view like
        # any other data type.
        if isinstance(data, APIResponse):
            self.data, self.http_status, self.http_headers = \
                data.data, data.http_status, data.http_headers
        # Same goes for errors, which are basically response objects in
        # exception form; we copy the http metadata, however keep the exception
        # instance itself as the data, so it can be identified as an error.
        elif isinstance(data, APIError):
            self.data, self.http_status, self.http_headers = \
                data, data.http_status, data.http_headers
        # Otherwise, just use the parameters passed.
        else:
            self.data, self.http_status, self.http_headers = data, None, None

        # the metadata passed directly to us always overwrites what might have
        # been copied from ``data``.
        if http_status is not None: self.http_status = http_status
        if http_headers is not None: self.http_headers = http_headers

    def get_response(self):
        """
        Returns a Django ``HttpResponse`` for this instance. Child classes have
        to implement ``format`` to modify the content of the response.
        """
        response = HttpResponse(self.format(self.data), status=self.http_status)
        if self.http_headers:
            for key, value in self.http_headers.items():
                response[key] = value
        return response

    def format(self, data):
        """
        Child classes need to provide this method to prepare ``data`` for use
        as the content of a ``HttpResponse``. Should return a string.

        Usually, ``data`` is base python structure that needs to be serialized.
        Although there are no precise requirements as to what datatypes need to
        be supported, the set of basic JSON types is recommended. Note that
        the ``data`` can also be ``None``, which should translate to an empty
        response body in almost all cases.

        ``data`` can also be of be an exception (of type ``APIError``), in
        which case it should be formatted as an error response.
        """
        raise NotImplementedError()
            
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

    # Child classes can specify this
    default_response_class = None

    # TODO: Do we want to support allowing/disallow authenticiation (key and
    # other) via headers or arguments. It's currently configured via the Meta
    # subclasses of an API, which is pretty flexible, but logicially it might
    # belong at the dispatcher level?
    def __init__(self, api, response_class=default_response_class):
        self.api = api
        self.response_class = response_class

    def __call__(self, *args, **kwargs):
        return self.dispatch(*args, **kwargs)

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
        raise a ``BadRequestError``.
        """
        raise NotImplementedError()
    del parse_request

    def dispatch(self, request, url=None):
        """
        Resolves an incoming request to an API call, calls the method, and
        returns it's result, converted via the ``response_class`` attribute,
        as a Django ``Response`` object.

        ``request`` is a Django ``Request`` object. ``url`` is the sub-url of
        the request to be resolved. If it is missing, ``request.path`` is used.
        """
        if not hasattr(self, 'parse_request'):
            raise NotImplementedError()

        method = None
        try:
            parsed = self.parse_request(request, url or request.path)
            if isinstance(parsed, tuple): parsed = [parsed]

            # try to resolve to a method call by trying all the
            # different options in order
            method = None
            for path, args, kwargs in parsed:
                method = self.api.resolve(path)
                if method: break;
            if method is None:
                raise MethodNotFoundError()

            # helper that returns the first "not None" item of a sequence
            first = lambda *a: filter(lambda x: x is not None, a)[0]

            # validate api key: first, check if we we need to require a key at
            # all, and if so, what the function doing the validation is. if
            # there is no method-specific validator, try the one from the
            # namespace. note that ``False`` means key auth is not required
            # for this call.
            meta = method._namespace._meta
            check_key = getattr(method, 'check_key', None)
            if check_key is None:
                check_key = meta.check_key
            # find the correct key to use, from arguments and http headers
            if check_key:
                key = kwargs.pop(first(meta.key_argument, 'apikey'), None) or \
                      request and request.META.get(first(meta.key_header, 'X-APIKEY'))
                if not check_key(request, key):
                    raise InvalidKeyError()

            # handle pre-processing
            process_call = getattr(method, 'process_call', None)
            if process_call is None:
                process_call = meta.process_call
            # If a pre-processors was found, call it first. call processors
            # may raise exceptions, or return a new ``apimethod`` object
            # that will be called instead. Additionally, a return value of
            # ``True`` will have no effect, while ``False`` will cause an
            # exception to be raised.
            # note that we cannot let the processor call the api view itself.
            # As ``None`` is a valid response for api views, we would not be
            # able to determine whether that has been done or not.
            if process_call:
                process_result = process_call(request, method, args, kwargs)
                if process_result is False:
                    raise BadRequestError()
                elif process_result is True:
                    pass
                elif process_result:
                    method = process_result

            # call the first method found
            try:
                # TODO: Check and compare method signatures to allow for more
                # detailed error messages ("argument X not supported" etc.)
                # finally, call the function itself.
                result = method(request, *args, **kwargs)
            except TypeError, e:
                raise BadRequestError()

        # Catch our own errors only. Everything else will bubble up to Django's
        # exception handling. If you don't want that, you can always write a
        # custom dispatcher and let it handle or preprocess the rest (e.g.
        # convert all exceptions to ``APIError``s before passing them along).
        except APIError, e:
            # try to find a custom error formatting function
            meta = method and method._namespace._meta or self.api._meta
            if meta.format_error:
                e.data = meta.format_error(request, e)
            # use the exception as the data object; response classes need to
            # be able to handle that.
            result = e

        response_class = self.response_class
        # if no response class is available (which usually means that the user
        # as explicitly passed ``None``, as dispatcher should provide a
        # default response class, then we return everything raw
        if not response_class:
            from response import PythonResponse
            response_class = PythonResponse

        return response_class(result).get_response()