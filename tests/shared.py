"""
Tests for GenericAPI.
"""

if __name__ == "__main__":
    # Running this test file with py.test won't work, because py.test tries
    # to import the complete djutils module from the root level, which results
    # in Django modules being imported, which require configured settings.
    # To make those available, execute this file directly. We then prepare
    # a dummy django environment and let pytest handle it from there.
    from django.conf import settings
    settings.configure()

    from py.test import cmdline
    import sys
    sys.exit(cmdline.main(['test.py'] + sys.argv[1:]))


from py.test import raises
from djutils.features.genericapi import *

class SampleAPI(GenericAPI):
    def check_key(): pass
    def check_auth(user, pw): pass

    # root namespace
    @expose
    def register(name): return True

    class test(Namespace):
        @expose
        def echo(text): return text

        # Not, or not always exposed
        def notexposed(): pass
        @conceal
        def concealed(): pass
        def __private(): pass

class ExposeAllAPI(SampleAPI):
    expose_by_default = True

def test_accessibility():
    """Make sure we can and cannot access the right functions."""

    # root-level methods
    raises(Exception, SampleAPI.execute, 'test.register')
    # invalid methods
    SampleAPI.execute('does.not.exist')

    # exposed & concealed in standard mode
    SampleAPI.execute('test.notexposed')
    SampleAPI.execute('test.concealed')
    SampleAPI.execute('test.__private')

    # exposed & concealed in "expose by default" mode
    SampleAPI.execute('test.notexposed')
    SampleAPI.execute('test.concealed')
    SampleAPI.execute('test.__private')