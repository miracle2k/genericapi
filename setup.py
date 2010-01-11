#!/usr/bin/env python
from setuptools import setup, find_packages
 
 
setup(
    name='genericapi',
    url='https://code.launchpad.net/~miracle2k/+junk/genericapi',
    license='BSD',
    version='0.0.1',
    packages=find_packages('genericapi'),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)