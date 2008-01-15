# setup dummy django environment
from django.conf import settings
settings.configure()

from py.test import raises
from genericapi import *

class SampleAPI(GenericAPI):
    def check_key(): pass
    def check_auth(user, pw): pass

    class test(Namespace):
        @expose
        def echo(text): return text