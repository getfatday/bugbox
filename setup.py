#!/usr/bin/env python
# encoding: utf-8

"""
Created by Ian Anderson on 2009-09-15.
"""

import os
from setuptools import setup

setup(name = "bugbox",
    version = '0.0.2',
    description = "Bugbox utilities module",
    author = "Ian Anderson",
    author_email = "getfatday@gmail.com",
    url = "http://github.com/getfatday/bugbox",
    packages = ['bugbox','bugbox/shell',],
    scripts = ["bin/bugbox"],
    long_description = "BugBox is a application used to post integration requests associated with external bug systems",
    test_suite = "test.run",
    dependency_links = [
      "http://github.com/getfatday/ducksoup/downloads",
    ],
    install_requires = [
      'Genshi>=0.5',
      'CherryPy>=3.1.2',
      'ducksoup>=0.0.1'
    ],
    data_files = [(os.path.join("bugbox", r), [os.path.join(r, f) for f in fs] ) for r, ds, fs, in os.walk('shared')],
    entry_points="""
    [bugbox.plugin.command]
    command.help = bugbox.shell.help:Help
    command.version = bugbox.shell.version:Version
    command.hook = bugbox.shell.hook:Hook
    [bugbox.plugin.hook]
    command.update = bugbox.shell.hook:Update
    """,
)