#!/usr/bin/env python
# encoding: utf-8

import os
import optparse
import sys
from ducksoup.plugin import IPlugin, plugin

class ICommand(IPlugin):

  helpSummary = ""
  help = ""
  name = ""
  OptionParser = None
  
  def parse(self, *args): pass
  def error(self, msg, code=1): pass
  def usage(self): pass
  def execute(self, opt, args): pass

class Command(plugin):
  """Base class for any command line action in BugBox.
  """
  __entry_point__ = "bugbox.plugin.command"
  __interface__ = ICommand
  _optparse = None
  _tag = "bugbox"
  
  helpSummary = ""
  
  def __init__(self, path=None):
    self._name = None
    self._help = None
    self._path = path
    
  @property
  def path(self):
    if self._path:
      return "%s %s" % (self._path, self.name)
    
    return self.name
    
  @property
  def help(self):  
    if self._help == None:
      self._help = """%s %s

%s""" % (self.path, self.helpUsage, self.helpDescription)
    return self._help

  @property
  def name(self):
    if self._name == None:
      self._name = self.__class__.__name__.lower().replace('_', '-')
    return self._name

  @property
  def OptionParser(self):
    if self._optparse is None:        
      self._optparse = optparse.OptionParser(usage = self.help)
      self._options(self._optparse)
    return self._optparse
    
  def parse(self, *args):
    return self.OptionParser.parse_args(list(args))
    
  def error(self, msg, code=1, usage=True):
    if usage:
      self.OptionParser.error(msg)
    else:
      print >> sys.stderr,  "%s: error: %s" % (self.path, msg)
      
    sys.exit(code)

  def _options(self, p):
    """Initialize the option parser.
    """

  def usage(self):
    """Display usage and terminate.
    """
    self.OptionParser.print_help()

  def execute(self, opt, args):
    """Perform the action, after option parsing is complete.
    """
    raise NotImplementedError
  
class TreeCommand(Command):

  def __init__(self, path=None):
    Command.__init__(self, path)
    self._commands = None

  @property
  def commands(self):
    if self._commands == None:
      self._commands = {}
      for entry in self.entries:
        e = entry(path=self.path)
        self._commands[e.name] = e

    return self._commands

  @property
  def help(self):  

    cmds = self.commands    
    keys = cmds.keys()
    keys.sort()
    c_list = os.linesep.join([ "  %-14s %s" % (cmds[k].name, cmds[k].helpSummary) for k in keys ])


    if self._help == None:
      self._help = """%s [options] [command]

%s

Commands:
%s""" % (self.name, self.helpSummary, c_list)
    return self._help

  def parse(self, *args):

    args = list(args)

    cmd = None
    for i in range(len(args)):
      if args[i] in self.commands.keys():
        cmd = args[i:]
        args = args[:i]
        break

    options = list(self.OptionParser.parse_args(args))
    options[1] = cmd

    return tuple(options)

  def execute(self, opt, args):

    if args == None:
      args = []
    else:
      args = list(args)

    if len(args) > 0:
      cmd = args[0]
      args = args[1:]
    else:
     cmd = None

    if cmd != None:
      if self.commands.has_key(cmd):
        cmd = self.commands[cmd]
      else:
        self.error("Command '%s' is unknown" % cmd)
        exit(1)

      try:
        c_opt, c_args = cmd.parse(*args)
        cmd.execute(c_opt, c_args)
      except NotImplementedError:
        self.error("The command '%s' has not been implemented yet" % cmd.name)
        exit(1)
    else:
      self.error("No options or commands provided")
    
class BugBox(TreeCommand):

  helpSummary = "Utilities to query and manage a BugBox repository"

  def _options(self, p):
    p.add_option('-V', '--version', help='display version of BugBox',
                 dest='version', action='store_true')

  def execute(self, opt, args):

    if args == None:
      args = []
    else:
      args = list(args)

    if opt.version:
      args = ["version",]
      
    TreeCommand.execute(self, opt, args)