import re
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
        super(BadJsonError, self).__init__(*args, **kwargs)
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
    """
    default_response_class = JsonResponse
    # TODO: allow simple strings option
    # TODO: allow GET params option

    ident_regex = re.compile('^[_a-zA-Z][_a-zA-Z0-9]*$')

    def __parse(self, request, path, argstr=None):
        from django.utils import simplejson

        # convert the positional argument from json to python
        if argstr:
            try: args = [simplejson.loads(argstr)]
            except ValueError, e: raise BadJsonError(argstr)
        else:
            args = []

        # convert json query strings into kwargs array
        kwargs = {}
        for key, value in request.GET.items():
            try: kwargs[str(key)] = simplejson.loads(value)
            except ValueError, e: raise BadJsonError(value)
        return [(path, args, kwargs,)]

    def parse_request(self, request, url):
        """
        Although we not have two we always return a list (of call-data
        tuples) - even if there is only one option. This makes it easier for
        the ``RestDispatcher`` class that uses us as a base.
        """
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
                return (option1 or []) + self.__parse(request, path[:])

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