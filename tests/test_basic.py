from shared import *

def test_class():
    """
    General class/metaclass related tests.
    """
    
    # non-namespace subclasses are untouched, it's methods not made static
    class TestAPI(GenericAPI):
        class SortedDict(dict):
            def sort(self): self.items()
    TestAPI.SortedDict().sort()
    
    # instances are not allowed
    raises(TypeError, TestAPI)
    
    # [bug] make sure we keep the correct name
    SampleAPI.test.__name__ = 'test'

def test_accessibility():
    """Make sure we can and cannot access the right functions."""

    class TestAPI(GenericAPI):
        @expose
        def root(): return True
    
        class sub(Namespace):
            @expose
            def exposed(): pass
            def notexposed(): pass
            @conceal
            def concealed(): pass
            def __private(): pass

    def can_call(apicls, name, *args, **kwargs):
        apicls.execute(name, *args, **kwargs)
    def cannot_call(apicls, name, *args, **kwargs):
        raises(AttributeError, apicls.execute, name, *args, **kwargs)

    # root-level methods
    can_call(TestAPI, 'root')
    # invalid methods
    cannot_call(TestAPI, 'does.not.exist')
    
    # exposed & concealed in standard mode
    can_call(TestAPI, 'sub.exposed')
    cannot_call(TestAPI, 'sub.notexposed')
    cannot_call(TestAPI, 'sub.concealed')
    cannot_call(TestAPI, 'sub.__private')

    # exposed & concealed in "expose by default" mode
    TestAPI.expose_by_default=True
    can_call(TestAPI, 'sub.exposed')
    can_call(TestAPI, 'sub.notexposed')
    cannot_call(TestAPI, 'sub.concealed')
    cannot_call(TestAPI, 'sub.__private')
    cannot_call(TestAPI, 'sub._sub__private')
    
    # path must be a method, not a namespace (or anything else)
    cannot_call(TestAPI, 'sub')