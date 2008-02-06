from shared import *

class SampleAPI(GenericAPI):
    class Meta:
        expose_by_default = True
        #check_auth = login_required
        #auth_header = ('X-APIUSER')
        #def check_auth(request, user, password):
        #    pass

        key_header = 'X-APIKEY'
        key_argument = 'apikey'
        def check_key(request, key):
            print key
            return key == '1'
        
    def noop(r):
        return None
        
def test_key_auth():
    """
    Test the API key system.
    """
    
    assert SampleAPI.execute('noop', apikey="1") == None