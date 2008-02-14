import re
from core import Dispatcher, BadRequestError
from response import *

__all__ = (
    'SimpleDispatcher', 'JsonDispatcher',
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