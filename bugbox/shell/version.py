#!/usr/bin/env python
# encoding: utf-8
import os
import sys

from bugbox.shell import Command
from bugbox import __version__ as version

class Version(Command):
  
  helpSummary = "Returns the version number of %s" % Command._tag
  helpUsage = """[options]"""
  helpDescription = """
Returns the version number of %s
""" % Command._tag
    
  def execute(self, opt, args):
    print "%s %s" % (self._tag, version)

