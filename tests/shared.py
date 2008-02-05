# setup dummy django environment
from django.conf import settings
settings.configure()

from py.test import raises
from genericapi import *