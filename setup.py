#!/usr/bin/env python
# encoding: utf-8

"""
Created by Ian Anderson on 2009-09-15.
"""

import os
from setuptools import setup
from bugbox import __version__ as version
from bugbox import __doc__ as long_description

setup(name = "bugbox",
    version = version,
    description = "Bugbox utilities module",
    author = "Ian Anderson",
    author_email = "getfatday@gmail.com",
    url = "http://github.com/getfatday/bugbox",
    packages = ['bugbox',],
    long_description = long_description,
    test_suite = "test.run",
    install_requires = [
      'Genshi>=0.5',
      'CherryPy>=3.1.2',
    ],
    data_files = [(os.path.join("bugbox", r), [os.path.join(r, f) for f in fs] ) for r, ds, fs, in os.walk('shared')]
)