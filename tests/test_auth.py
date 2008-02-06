from django.http import HttpRequest, QueryDict
from shared import *

#check_auth = login_required
#auth_header = ('X-APIUSER')
#def check_auth(request, user, password):
#    pass

def make_request(key, value):
    r = HttpRequest()
    r.META[key] = value
    return r

class SampleAPI(GenericAPI):
    class Meta:
        expose_by_default = True
        def check_key(request, key): return key in ['123', '456', '789']
    class sub(Namespace):
        class Meta:
            def check_key(request, key): return key in ['abc', 'def']
        def test(r): return True
    def test(r): return True
    @check_key(False)
    def public(r): return True
    @check_key(lambda r, key: key == 'abcdefg')
    def custom(r): return True
        
def test_key_auth():
    """
    Test the API key system.
    """
    
    # root level, valid key
    assert SampleAPI.execute('test', apikey="123") == True
    # root level, invalid key
    raises(InvalidKeyError, SampleAPI.execute, 'test', apikey="zzz")
    
    # namespace, separate check_key, valid key
    assert SampleAPI.execute('sub.test', apikey="abc") == True
    # namespace, separate check_key, invalid key
    raises(InvalidKeyError, SampleAPI.execute, 'sub.test', apikey="zzz")
    
    # make sure the same thing works with headers as well
    assert SampleAPI.execute('test', request=make_request('X-APIKEY', '123')) == True
    raises(InvalidKeyError, SampleAPI.execute, 'test', request=make_request('X-APIKEY', 'zzz'))
    
    # make sure key passsed via argument take precedence
    assert SampleAPI.execute('sub.test',
                             apikey='abc',    # right
                             request=make_request('X-APIKEY', 'zzz') # wrong
                                ) == True
    # only the first key found is used; other's are not tried, regardless
    # whether the first fails or not
    raises(InvalidKeyError, SampleAPI.execute, 'sub.test',
        apikey='zzz',    # wrong
        request=make_request('X-APIKEY', 'abc') # right, but not used
            ) == True
    
    # method-level @check_key modifiers work
    assert SampleAPI.execute('custom', apikey="abcdefg") == True
    assert SampleAPI.execute('public') == True
    # if key check is disabled on a method level but the request contains an
    # API key nevertheless, the key is not checked, and not removed from the
    # arguments either. this is a design decision, motivated by the reasoning
    # that a user can implement a dummy key validator that always returns True,
    # if he wants different behaviour. the alternative would be for the API
    # to remove the argument automatically if key validation is enabled on a
    # namespace level and disabled on a key-level.
    raises(BadRequestError, SampleAPI.execute, 'public', apikey='abc')
    
    # passing the key via an argument can be disabled
    SampleAPI._meta.key_argument = False
    raises(InvalidKeyError, SampleAPI.execute, 'sub.test', apikey="abc")
    # still works via header
    assert SampleAPI.execute('sub.test', request=make_request('X-APIKEY', 'abc')) == True
    
    # make sure header can be disabled
    SampleAPI._meta.key_argument = None   # go back to default from previous test
    SampleAPI._meta.key_header = False
    raises(InvalidKeyError, SampleAPI.execute, 'test', request=make_request('X-APIKEY', '123'))
    # still works via argument
    assert SampleAPI.execute('test', apikey="123") == True
    
    # with a custom key argument
    SampleAPI._meta.key_argument = 'the_key'
    assert SampleAPI.execute('sub.test', the_key="abc") == True

    # with a custom key header
    SampleAPI._meta.key_header = 'MYAPIKEY'
    assert SampleAPI.execute('test', request=make_request('MYAPIKEY', '123')) == True
    
    # make sure it works if sub doesn't have it's own check_key
    SampleAPI._meta.key_argument = None   # reset from previous test
    SampleAPI.sub._meta.check_key = None
    assert SampleAPI.execute('sub.test', apikey="123") == True