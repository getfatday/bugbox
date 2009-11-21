#!/usr/bin/env python
# encoding: utf-8
"""
help.py

Created by Ian Anderson on 2009-09-15.
"""

import os
import sys

from bugbox.shell import Command, TreeCommand
from bugbox import debug, BugBox, TAIL, STAMP

class Hook(TreeCommand):

  __entry_point__ = "bugbox.plugin.hook"
  helpSummary = "GIT Hooks for a BugBox repository"


class Pre_Receive(Command):
  
  helpSummary = "Use in GIT pre-receive hook to integrate BugBox"
  helpUsage = """<ref> <oldrev> <newrev>"""
  helpDescription = """Use in GIT pre-receive hook to integrate BugBox.

Checks that reference names are valid and then calls system specific hook. A
executable system hook should be placed in your GIT_DIR/hooks directory with a 
name of pre-receive.<system name>.

For example:

GIT_DIR/hooks/pre-receive.jira"""
    
  def execute(self, opt, args):
    
    # Make sure we are running through a GIT hook
    if not os.environ.has_key("GIT_DIR") or len(os.environ["GIT_DIR"]) == 0:
      self.error("""Don't run this script from the command line.
 (if you want, you could supply GIT_DIR then run
  %s <ref> <oldrev> <newrev>)""" % self.path, usage=False)
      
    # Make sure all the necesarry arguments have been passed
    if len(args) < 3:
      self.error("Usage: %s <ref> <oldrev> <newrev>" % self.path)
      
    refname, oldrev, newrev = args[0:3]
    
    bbox = BugBox(os.environ["GIT_DIR"])
    
    # Be sure systems have been configured
    if len(bbox.systems.keys()) == 0:
      self.error("""
The GIT configuration on the repository you are updating does not contain any 
BugBox ticket systems. Please add a ticket system to your configuration.

For example in your GIT config add:

[ticket 'bz']
name=BugZilla
url=http://bugzilla.example.com

""", usage=False)

    if not refname.startswith("refs/heads"):
      self.error("""
    BugBox only allows users to push to head references using the format of 
    system/ticket-number/label.

    For Example:

    %(name)s/12345/default
    %(name)s/12345/AlarmClock

    """ % {"name": bbox.systems.keys()[0]}, usage=False)
    
    system, ticket, label = bbox.splitref(refname)
    
    # Be sure reference is valid
    if not system:
      self.error("""Reference name '%(ref)s' is not valid.
      
Please use the format system/ticket-number/label:

For Example:

%(name)s/12345/default
%(name)s/12345/AlarmClock

""" % {"ref": refname, "name": bbox.systems.keys()[0]}, usage=False)

    # Be sure system is valid
    if system not in bbox.systems.keys():
      self.error("""Ticket system '%s' is unknown.

Please use one of the following:

%s
""" % (system, os.linesep.join(["%-8s<%s %s>" % (k, bbox.systems[k].name, bbox.systems[k].url) for k in bbox.systems.keys()])), usage=False)

    
    # Call any system hooks
    hook = os.path.join(bbox.path, "hooks", "pre-receive.%s" % system)
            
    if os.path.exists(hook) and os.access(hook, os.X_OK):
      
      o, e, v = bbox.call(hook, *args)
      
      print o
      
      if v != 0:
        if e:
          self.error("%s: %s" % (hook, e), code=v, usage=False)
        else:
          self.error(hook, code=v, usage=False)

    #Set tail if one does not exist
    tag_ref = refname.replace("refs/heads", "refs/tags/%s" % TAIL)
    
    if not bbox.has_ref(tag_ref):
      bbox.set_tail(refname, newrev)

    #Touch the .bugbox file for modification time updates. 
    #Saves us from searching the refs directory
    stamp = os.path.join(bbox.path, STAMP)
    with file(stamp, 'a'):
      os.utime(stamp, None)
        
        
