from shared import *
from genericapi.core import Dispatcher

def make_request(url):
    r = HttpRequest()
    url = urlparse(url)
    r.GET = QueryDict(url.query)
    r.path = url.path
    return r

class SampleAPI(GenericAPI):
    expose_by_default = True
    def noop(request): return None
    def give_me_true(request): return True
    def negate_bool(request, b): return not b
    def add(request, a, b): return a+b
    def make_list(request, *args): return list(args)
    def make_dict(request, **kwargs): return kwargs
    def echo(request, val): return val
    class ns(Namespace):
        def give_me_false(request): return False

    def __format_error(e):
        return 
    def complex(request, a):
        if a is None:
            raise APIError('must specify a')

def test_common():
    """Common response stuff"""

    # make sure we can create APIResponse with the http_status etc. metadata
    # make sure we can create APIResponse with APIError and APIResponse data,
    # and that http metadata takes precedence correctly.
    pass
    
def test_python_response():
    # make sure normal and api errors are passed out
    # make sure http status stuff is ignored, and that it works with ApiResponse data
    pass

def test_json_response():
    # make sure basic formatting works, using APIResponse directly (error and not error, and queryset), and None
    # make sure it works with a dispatcher context, using some basic calls.
    pass