#!/usr/bin/env python

from distutils.core import setup
from unifi import version

setup(
    name = 'unifi-cam-proxy',
    version = version.__version__,
    description = 'Unifi NVR-compatible camera proxy',
    long_description = open('README.rst').read() + '\n\n' + open('HISTORY.rst').read(),
    author = 'Keshav Varma',
    entry_points = {
        'console_scripts': ['unifi-cam-proxy=unifi.main:main'],
    }
    # url = 'TODO: Enter an URL',
    # packages = [
    #     'TODO: Enter package(s)'
    # ],
    # classifiers = [
    #     'TODO: Add trove classifiers (http://pypi.python.org/pypi?%3Aaction=list_classifiers)'
    # ]
)
