"""
Test error handling (maybe merge with basic?)

 * custom error formatting is called and works
 * APIError http_status etc. works
"""

from shared import *

def test_apierror_class():
    """
    Basic functionality tests for ``APIError``.
    """
    
    # make sure APIError provides default formatting
    assert APIError('error', code=2).data is not None
