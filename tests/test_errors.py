"""
Test error handling.
"""

from shared import *
from genericapi.core import Dispatcher
from genericapi.response import JsonResponse

class SampleAPI(GenericAPI):
    class Meta:
        expose_by_default = True
        
    def fail(request):
            raise APIError('you requested an error.')
    
    class custom_err(Namespace):
        class Meta:
            def format_error(request, error):
                error.http_status = 555
                error.custom_arg = True
                return {'error': True,
                        'desc': error.message,
                        'num': error.code}
        def fail(request):
            raise APIError('you requested an error.', code=99)

def test_apierror_class():
    """
    Basic functionality tests for ``APIError``.
    """
    
    # make sure APIError provides default formatting
    assert APIError('error', code=2).data is not None
    
    assert SampleAPI.execute('fail', response_class=JsonResponse).status_code == 500
    
def test_builtin_errors():
    """
    Test the built-in error types.
    """
    try: SampleAPI.execute('in.valid')
    except MethodNotFoundError, e:
        assert e.method == ['in', 'valid']

def test_custom_formatting():
    """
    Test the ``format_error`` hook.
    """
    
    try: SampleAPI.execute('custom_err.fail')
    except Exception, e:
        assert e.data['error'] == True
        assert 'desc' in e.data
        assert e.data['num'] == 99
        # hook can modified the error instance directly
        assert e.http_status == 555
        assert e.custom_arg == True