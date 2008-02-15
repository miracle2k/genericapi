"""
Test error handling.
"""

from shared import *
from genericapi.core import Dispatcher

class SampleAPI(GenericAPI):
    class Meta:
        expose_by_default = True
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
    
def test_builtin_errors():
    """
    Test the built-in error types.
    """
    assert MethodNotFoundError(method=['test']).method == ['test']

def test_custom_formatting():
    """
    Test the ``format_error`` hook.
    """
    
    try: SampleAPI.execute('fail')
    except Exception, e:
        assert e.data['error'] == True
        assert 'desc' in e.data
        assert e.data['num'] == 99
        # hook can modified the error instance directly
        assert e.http_status == 555
        assert e.custom_arg == True