#!/usr/bin/env python
# encoding: utf-8

import os
import sys

from bugbox.shell import Command

class Help(Command):
  
  helpSummary = "Displays help information for %s" % Command._tag
  helpUsage = """[options]"""
  helpDescription = """
Displays help information for %s
""" % Command._tag
    
  def execute(self, opt, args):
    from bugbox.shell import BugBox
    
    bugbox = BugBox()
    bugbox.usage()