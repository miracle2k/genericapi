from shared import *

# helper functions for testing api calls.
def can_call(apicls, name, *args, **kwargs):
    expect = kwargs.pop('expect', True)
    assert apicls.execute(name, *args, **kwargs) == expect
def cannot_call(apicls, name, *args, **kwargs):
    raises(AttributeError, apicls.execute, name, *args, **kwargs)

def test_class():
    """
    General class/metaclass related tests.
    """
    
    # non-namespace subclasses are untouched, it's methods not made static and
    # they can be instantiated.
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
    
        class other(object):  # non-namespace
            @expose
            def func1(): return True
            @staticmethod
            @expose
            def func2(): return True
    
        class sub(Namespace):
            @expose
            def exposed(): return True
            def notexposed(): return True
            @conceal
            def concealed(): return True
            def __private(): return True

    # root-level methods
    can_call(TestAPI, 'root')
    # invalid methods
    cannot_call(TestAPI, 'does.not.exist')
    # non-namespace methods can't be called
    cannot_call(TestAPI, 'other.func1')
    cannot_call(TestAPI, 'other.func2')
    
    # exposed & concealed in standard mode
    can_call(TestAPI, 'sub.exposed')
    cannot_call(TestAPI, 'sub.notexposed')
    cannot_call(TestAPI, 'sub.concealed')
    cannot_call(TestAPI, 'sub.__private')
    cannot_call(TestAPI, 'sub._sub__private')

    # exposed & concealed in "expose by default" mode
    TestAPI.expose_by_default = True
    can_call(TestAPI, 'sub.exposed')
    can_call(TestAPI, 'sub.notexposed')
    cannot_call(TestAPI, 'sub.concealed')
    # private functions can never be called, even when exposed
    cannot_call(TestAPI, 'sub.__private')
    cannot_call(TestAPI, 'sub._sub__private')
    
    # make sure path can only be a method, not a namespace (or anything else)
    cannot_call(TestAPI, 'sub')

def test_inheritance():
    """
    Make sure inheritance works.
    """
    class TestAPI(GenericAPI):
        @expose
        def root(): return True
        class sub(Namespace):
            @expose
            def exposed(): return True
            @expose
            def other(): return True
    class TestAPIEx(TestAPI):
        @expose
        def subclass_method(): return True
        class subex(TestAPI.sub): pass

    # direct call to method in child class
    can_call(TestAPIEx, 'subclass_method')
    # call to method in super class
    can_call(TestAPIEx, 'root')
    # call to method in super class of a namespace
    can_call(TestAPIEx, 'subex.exposed')
    # call to method in a namespace of a super class
    can_call(TestAPIEx, 'sub.exposed')
    
    # check that super class methods can be hidden by override
    class TestAPIEx2(TestAPI):
        class sub(TestAPI.sub):
            @expose
            def exposed(): return 5
    can_call(TestAPIEx2, 'sub.exposed', expect=5)
    # check that the same is true if a namespace just has the same name as one
    # in the super class, and does not directly inherit from it as well.
    class TestAPIEx3(TestAPI):
        class sub(Namespace):
            @expose
            def exposed(): return 5
    can_call(TestAPIEx3, 'sub.exposed', expect=5)
    
    # [bug] makes sure backtracking works while resolving methods. the child
    # class has 'sub', but not 'other", so the code needs to go back and check
    # the super classes for a "sub" namespace with an "other" method.
    can_call(TestAPIEx3, 'sub.other')
    # the same should be true of a certain node turns out to exist, but is
    # not exposed or otherwise not valid.
    class TestAPIEx4(TestAPIEx3):
        class sub(Namespace):
            other = 'test'
            # is actually not exposed, but is in superclass!
            def exposed(): return 10
    can_call(TestAPIEx4, 'sub.other')
    can_call(TestAPIEx4, 'sub.exposed', expect=5)
    
    # simple multi-inheritance checks
    class TestAPIEx5(TestAPI, SampleAPI):
        @expose
        def new(): return True
    can_call(TestAPIEx5, 'test.echo', 'foo', expect='foo')
    can_call(TestAPIEx5, 'sub.exposed')
    can_call(TestAPIEx5, 'new')
    
    # expose_by_default should only affect the class it is set in (and child
    # namespaces), but not super or child classes.
    class ApiA(GenericAPI):
        # expose_by_default defaults to False
        def notexposed_a(): return True
    class ApiB(ApiA):
        expose_by_default = True
        def notexposed_b(): return True
    class ApiC(ApiB):
        expose_by_default = False
        def notexposed_c(): return True
    cannot_call(ApiA, 'notexposed_a')
    can_call(ApiB, 'notexposed_b')
    cannot_call(ApiB, 'notexposed_a')
    cannot_call(ApiC, 'notexposed_a')
    can_call(ApiC, 'notexposed_b')
    cannot_call(ApiC, 'notexposed_c')