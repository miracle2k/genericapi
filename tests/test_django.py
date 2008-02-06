"""
Test django specific functionality

class AuthNamespace(Namespace):
    @expose
    def login(request, username, password):
        pass
        
    @expose
    def logout(request):
        pass
        
class LoginRequired(APIError): pass

class require_login(request, method, args, kwargs):
    if not check_session(request.session):
        raise LoginRequired()

"""