import re
from django.utils import simplejson
from core import Dispatcher, BadRequestError
from response import *

__all__ = (
    'SimpleDispatcher', 'JsonDispatcher', 'RestDispatcher',
)

class SimpleDispatcher(Dispatcher):
    """
    Dispatcher that resolves a path in dotted notation, mainly useful for
    debugging. Note the different method signature of ``dispatch``, and that
    ``request`` still needs to be passed in.

    Uses the free ``url`` argument of ``parse_request`` to pass along the
    method name and arguments, as the ``Dispatcher`` base class is not really
    designed for this kind of use, and doesn't provide a really good way to
    handle any other incoming data besides the request. The best alternative
    would probably be attaching custom attributes to ``request``, but it could
    possibly be ``None`` as well.
    """
    def parse_request(self, request, data):
        return (data['name'].split('.'), data['args'], data['kwargs'])

    def dispatch(self, name, request=None, *args, **kwargs):
        data = {'name': name, 'args': args, 'kwargs': kwargs}
        return super(SimpleDispatcher, self).dispatch(request, data)
    
class BadJsonError(BadRequestError):
    """
    Thrown by the JSON dispatcher if it encounters an invalid JSON value.
    """
    def __init__(self, value, *args, **kwargs):
        BadRequestError.__init__(self, *args, **kwargs)
        self.value = value
        if self.value:
            self.message = 'Invalid JSON (%s)'%self.value

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
    
    Supports additional arguments: If ``jquery_compat`` is used, an ``_``
    argument, if passed, will be ignored. It is used by jQuery to force no
    caching by passing a timestamp.
    
    ``jsonp_callback`` contains the name of the parameter that can be used to
    specify a callback function: It will not be a part of the method arguments.
    If not set then callbacks will be disabled. Defaults to 'jsonp'.
    """
    default_response_class = JsonResponse
    # TODO: allow simple strings option
    # TODO: allow GET params option

    ident_regex = re.compile('^[_a-zA-Z][_a-zA-Z0-9]*$')
    
    def __init__(self, *args, **kwargs):
        self.jquery_compat = kwargs.pop('jquery_compat', False)
        self.jsonp_name = kwargs.pop('jsonp_callback', 'jsonp')
        super(JsonDispatcher, self).__init__(*args, **kwargs)
    
    def make_response(self, request, response_class, *args, **kwargs):
        # if used with a JsonResponse, pass along the jsonp callback value
        if response_class is JsonResponse:
            kwargs = kwargs.copy()
            kwargs['jsonp_callback'] = getattr(request, '_jsonp_callback', False)
        return super(JsonDispatcher, self).make_response(
            request, response_class, *args, **kwargs)

    def __parse(self, request, kwargs, path, arg=None):
        """
        Helper function that tries to JSON-parse the value in ``arg`` and
        then returns everything as a call-tuple. This utility function is
        used by ``parse_request`` and required because it's not always clear
        if the last part of an URL is a method name or a positional argument,
        so we often have to return multiple call-tuples.
        """
        if arg:
            try: args = [simplejson.loads(arg)]
            except ValueError, e: raise BadJsonError(arg)
        else:
            args = []

        return [(path, args, kwargs,)]

    def parse_request(self, request, url):
        """
        Although we not have to we always return a list (of call-data
        tuples) - even if there is only one option. This makes it easier for
        the ``RestDispatcher`` class that uses us as a base.
        """
        # We may return multiple call tuples, but the query string / kwargs
        # part is always the same, so for performance reasons why parse those
        # only once time up front (instead of in ``__parse``.
        querystrings = dict(request.GET.items())
        # Start by handling some special arguments first. In the case of
        # ``jsonp``, the fact that this is pretty much the first thing we do
        # also means that if an error occurs during argument parsing,
        # jsonp-mode will already be active, and the error result will be
        # delivered as jsonp, too.
        # Assigning to ``request`` is kind of a hack, but currently pretty much
        # the only way to pass that value along until response-building.
        if self.jsonp_name:
            request._jsonp_callback = querystrings.pop(self.jsonp_name, False)
        if self.jquery_compat: querystrings.pop('_', None)
        # convert json query strings into kwargs array
        kwargs = {}
        for key, value in querystrings.items():
            try: kwargs[str(key)] = simplejson.loads(value)
            except ValueError, e: raise BadJsonError(value)
        
        # split the path and remove empty items
        path = filter(None, url.split('/'))
        if path:
            # Unless their are at least two items in path, there can not be any
            # arguments at all.
            if len(path) < 2:
                return self.__parse(request, kwargs, path, '')
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
                return self.__parse(request, kwargs, path[:-1], path[-1])
            # Otherwise, we can't say for sure if the last part is an attribute
            # or not, so we try to return both options. This is ok for the same
            # reasons outlined above: it cannot lead to the wrong call.
            else:
                # if an error is raised at this point for the argument option,
                # then we already know it can't work out, and leave it off.
                try: option1 = self.__parse(request, kwargs, path[:-1], path[-1])
                except BadRequestError: option1 = None
                return (option1 or []) + self.__parse(request, kwargs, path[:])

class RestDispatcher(JsonDispatcher):
    """
    Works like the JsonDispatcher with respect to arguments, but tries to
    push you towards restful api design by appending the HTTP method used to
    the call path.

    GET /comments/1
    ==> api.comments.get(1)

    DELETE /comments/1
    ==> api.comments.delete(1)

    PUT /comments/1
    {"text"}
    ==> api.comments.put(1,payload=[])

    POST /comments/
    {"text"}
    ==> api.comments.post(payload=[])

    Additional arguments can be used as well:

    GET /comments/1?full=true
    POST /comments/?mark_as_spam=true
    
    Ultimately, this means that you won't be able to call any method that does
    not end in get, post, put, or delete. If you want to offer a rest api in
    conjunction with other formats, you can create a separate child class for
    the rest dispatcher that implements the rest http methods as wrappers. That
    way, neither format will provide access the each others version of the API.
    """
    # TODO: support different payload parsers (xml, json, ...)

    def parse_request(self, request, url):
        options = super(RestDispatcher, self).parse_request(request, url)
        new_options = []
        for path, args, kwargs in options:
            # append http method to path
            path.append(request.method.lower())
            #  add post as payload
            if request.POST:
                kwargs['payload'] = request.POST
                
            new_options.append((path, args, kwargs,))
        return new_options