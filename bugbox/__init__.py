"""bugbox

BugBox is a application used to post integration requests associated with external bug systems.
"""

__version__ = '0.0.2'
__dist__ = 'git://github.com/getfatday/bugbox.git'

import cherrypy, os, subprocess, re, sys, hashlib, types, time, math, stat, tempfile
from datetime import tzinfo, timedelta, datetime
from email.utils import parsedate
from zipfile import ZipFile

STAMP = ".bugbox"
TAIL = "tails"
REF_PATTERN = re.compile(r"refs/(heads|tags/%s)/(?P<system>[^/]*)/(?P<number>[^/]*)(/(?P<label>.*))?" % TAIL)

def debug(test=None):

  if test == None or test:
    import pdb
    pdb.set_trace()

def profile(func):
    def newfunc(*args, **kwargs):
        startTime = time.time()
        result = func(*args, **kwargs)
        endTime = time.time()
        print """%s: %f %r %r""" % (func.__name__, endTime - startTime, args, kwargs)
        return result

    return newfunc

def pprint(l):
  
  if type(l) in (list, tuple):
    return " ".join([pprint(v) for v in l])
  if type(l) == dict:
    return " ".join(["%s=%s" % (pprint(k), pprint(v)) for k, v in l.items()])
  
  return str(l)

def log(func):
    def logging(*args, **kwargs):
      logger(func.__name__.upper(), args[1:], kwargs)
      return func(*args, **kwargs)

    return logging

if os.environ.has_key("BUGBOX_DEBUG") and os.environ["BUGBOX_DEBUG"].lower() in ("1", "yes", "y", "true"):
  def logger(*msg):
    cherrypy.log(pprint(msg))

else:
  def logger(*msg):
    pass

class cache_type(type):

  def __init__(cls, classname, bases, classdict):
    super(cache_type, cls).__init__(classname, bases, classdict)
    setattr(cls, '__cache__', {})

class Cache(object):
  
  __metaclass__ = cache_type

  def __init__(self, key=lambda x : x, synced=lambda x : True, sync=lambda x : None ):
    self.key = key
    self.synced = synced
    self.sync = sync

  @log
  def clear(self):
    self.__cache__ = {}
     
  def __call__(self, func):
    
    def cache(*args, **kwargs):
      
      key = self.key(args)
      
      if not self.synced(args):
        self.sync(args)
        self.clear()

      if not self.__cache__.has_key(func):
        self.__cache__[func] = {}

      if not self.__cache__[func].has_key(key):
        logger("CACHING", func, args, kwargs)
        self.__cache__[func][key] = func(*args, **kwargs)
        
      return self.__cache__[func][key]
      
    return cache

_cache = Cache(synced=lambda a : a[0].synced, sync=lambda a : a[0].sync())

def cache(func):
  return _cache(func)

class record_type(type):

  def __init__(cls, classname, bases, classdict):
    super(record_type, cls).__init__(classname, bases, classdict)
    setattr(cls, '__instances__', {})
    setattr(cls, '__indexed__', False)

class Record(object):

  __metaclass__ = record_type

  def __init__(self, provider):
    self._index = None
    self._provider = provider
    
  @property
  def synced(self):
    return self._provider.synced
    
  @property
  def provider(self):
    return self._provider
    
  @property
  def root(self):
    return self._provider[self.__class__]
    
  @property
  def isroot(self):
    return self == self.root
    
  @property
  def id(self):
    return self._index

  def obtain(self, index):
    
    obj = self.__class__(self._provider)
    obj._index = index
    self.root.__instances__[index] = obj
    
    return obj
    
  def values(self):
    return [self[k] for k in self.keys()]

  def items(self):
    
    return [(k, self[k]) for k in self.keys()]

  def __getitem__(self, key):
    
    if not self.has_key(key):
      raise KeyError("Key '%s' does not exist" % key)
    
    if self.root.__instances__.has_key(key):
      return self.root.__instances__[key]

    obj = self.obtain(key)
    return obj

  def sync(self):
    self._provider.sync()

  def has_key(self, key):
    return self.root.__instances__.has_key(key)

  def keys(self):
    return self.root.__instances__.keys()

class System(Record):
  
  def __init__(self, provider):
    Record.__init__(self, provider)

  def has_key(self, key):
    return Record.has_key(self, key) or \
           key in self.keys()

  def keys(self):
    return self.provider.system_keys()

  @property
  def name(self):
    return self.provider.parse_systems()[self.id]["name"]
    
  @property
  def url(self):
    return self.provider.parse_systems()[self.id]["url"]
    
  @cache
  def ticket_keys(self):
    return [k for k, v in self.provider.parse_tickets().items() if v["system"] == self.id]
    
  @property
  @cache
  def tickets(self):    
    return dict([(k, Ticket(self._provider)[k]) for k in self.ticket_keys()])


class Author(Record):
  
  def __init__(self, provider):
    Record.__init__(self, provider)
    self._noname = False

  def has_key(self, key):
    
    return Record.has_key(self, key) or \
           len(self.provider.commit_keys_by_author(key)) > 0 or \
           len(self.provider.commit_keys_by_committer(key)) > 0

  @property
  @cache
  def name(self):
    
    name = None

    if not self._noname:

      for k in self.provider.commit_keys_by_author(self.id):
        c = Commit(self._provider)[k]
        if c.author.name != None:
          name = c.author.name
          break
    
      if name == None:
        for k in self.provider.commit_keys_by_committer(self.id):
          c = Commit(self._provider)[k]
          if c.committer.name != None:
            name = c.committer.name
            break
      
      if name == None:
        self._noname = True
      
    return name
    
  @property
  def email(self):
    return self.id
    
  @property
  @cache
  def digest(self):
    return hashlib.md5(self.id).hexdigest()

  @property
  @cache
  def commits(self):
    return [Commit(self._provider)[key] for key in self.provider.commit_keys_by_committer(self.id)]

  @property
  @cache
  def authored(self):
    return [Commit(self._provider)[key] for key in self.provider.commit_keys_by_author(self.id)]

  def sync(self):
    self._noname = False
    Record.sync(self)

  @property
  @cache
  def labels(self):

    labels = {}

    for c in self.commits:
      for l in c.labels:
        if not labels.has_key(l.id):
          labels[l.id] = l

    return labels

  @property
  @cache
  def tickets(self):
    
    tickets = {}

    for l in self.labels.values():
      if not tickets.has_key(l.ticket.id):
        tickets[l.ticket.id] = l.ticket

    return tickets


class TZ(tzinfo):

  ZERO = timedelta(0)

  def __init__(self, offset):
    f = int(offset) * 0.01
    h = int(f)
    
    m = (( f - h ) * 100) + ( h * 60 )
    self._name = offset
    self.stdoffset = timedelta(minutes=m)

  def tzname(self, dt):
    return self._name

  def __repr__(self):
    return self._name
    
  def utcoffset(self, dt):
    return self.stdoffset
      
  def dst(self, dt):
    return self.ZERO

class UserStamp(object):
  
  def __init__(self, commit, name, epoch, tz, email=None):
    self._commit = commit
    self._name = name
    self._email = email
    self._digest = None
      
    self._user = None
      
    self._epoch = int(epoch)
    self._tz = tz
    self._date = None
    self._age = None

  @property
  def commit(self):
    return self._commit

  @property
  def name(self):
    return self._name
    
  @property
  def email(self):
    return self._email
    
  @property
  def digest(self):
    if self._digest is None and self._email:
      self._digest = hashlib.md5(self._email).hexdigest()

    return self._digest
    
  @property
  def user(self):
    
    if self._user == None and self._email:
      self._user = Author(self._commit._provider)[self._email]
      
    return self._user
    
  @property
  def age(self):
    
    if self._age == None:
      delta = time.time() - self._epoch
      
      if delta > 60*60*24*365*2:
        self._age = "%d years ago" % (delta/60/60/24/365)
      elif delta > 60*60*24*(365/12)*2:
        self._age = "%d months ago" % (delta/60/60/24/(365/12))
      elif delta > 60*60*24*7*2:
        self._age = "%d weeks ago" % (delta/60/60/24/7)
      elif delta > 60*60*24*2:
        self._age = "%d days ago" % (delta/60/60/24)
      elif delta > 60*60*2:
        self._age = "%d hours ago" % (delta/60/60)
      elif delta > 60*2:
        self._age = "%d minutes ago" % (delta/60)
      elif delta > 2:
        self._age = "%d second ago" % (delta)
      else:
        self._age = "right now"
      
    return self._age
    
  @property
  def date(self):
    if self._date == None:
      self._date = datetime.fromtimestamp(self._epoch, TZ(self._tz))
    return self._date
      
class DiffLine(object):
  
  def __init__(self, data, left=None, right=None):
    self.left = left
    self.right = right
    self.data = data
    
  def is_left(self):
    return self.left != None
    
  def is_right(self):
    return self.right != None
    
  def is_both(self):
    return self.is_left() and self.is_right()
      
class DiffChunk(object):
  
  def __init__(self, left_start, left_len, right_start, right_len, **kwargs):
    self.left_start = left_start
    self.left_len = left_len
    self.right_start = right_start
    self.right_len = right_len
    self.left_offset = 0
    self.right_offset = 0
    self.lines = []
    
  def append(self, event, data):
        
    pos_l = None
    pos_r = None
    
    if event in "- ":
      pos_l = self.left_start + self.left_offset
      self.left_offset += 1
    
    if event in "+ ":
      pos_r = self.right_start + self.right_offset
      self.right_offset += 1
    
    self.lines.append(DiffLine(data, pos_l, pos_r))
      
class FileDiff(object):
  
  def __init__(self, mode, action="U", format="ascii", tail=None, head=None, left=None, right=None, **kwargs):

    self.action = action
    self.format = format
    self.tail = tail
    self.head = head
    self.left = left
    self.right = right
    self.chunks = []
    
  @property
  def path(self):
    
    if self.right:
      return self.right
    else:
      return self.left
      
  def is_ascii(self):
    return self.format == "ascii"
    
  def is_binary(self):
    return self.format == "binary"
      
class UnifiedDiff(object):
  
  DIFF = re.compile(r"^diff --git (?P<left>.*) (?P<right>.*)$")
  INDEX = re.compile(r"^index (?P<tail>[^\.].*)\.\.(?P<head>[^ ]+)( (?P<mode>.*))?$")
  ACTION = re.compile(r"^(?P<action>deleted|old|new)( file)? mode (?P<mode>.*)$")
  BINARY = re.compile(r"^(?P<format>Binary) files .*$")
  COMMIT = re.compile(r"^(?P<commit>[a-z0-9]{40})$")
  CHUNK = re.compile(r"^@@ -(?P<left_start>[0-9]+)(,(?P<left_len>[0-9]+))? \+(?P<right_start>[0-9]+)(,(?P<right_len>[0-9]+))? @@$")
  LINE = re.compile(r"^(?P<event>\+|-| |@@ .* @@)(?P<data>.*$|$)")
  FILE = re.compile(r"^(\+\+\+|---) .*$")
  
  def __init__(self, data):
    self._data = data
    self._parsed_data = []
    self._commit_index = []
    self.files = []
    
    self._preparse()
    self._parse()
    
  def _parse(self):
    
    for f_data in self._parsed_data:
      
      f = FileDiff(**f_data)
      
      for c_data in f_data["chunks"]:
        c = DiffChunk(**c_data)
        
        for l_data in c_data["lines"]:
          c.append(**l_data)
                
        f.chunks.append(c)
      
      self.files.append(f)
  
  def _event(self, event, pattern, data):
    m = pattern.match(data)
    
    if not m:
      return False
      
    values = m.groupdict()
      
    if event == "commit":
      self._commit_index = values["commit"]
      
    if event == "diff":
      values["chunks"] = []
      
      for k in ("left", "right"):
        if values[k] == "/dev/null":
          del values[k]
        elif values[k][0] in "ab":
          values[k] = values[k][1:]
      
      self._parsed_data.append(values)
      
    if event == "action":
      
      if self._parsed_data[-1].has_key("action"):
        del values["action"]
      elif values["action"] == "deleted":
        values["action"] = "D"
      elif values["action"] == "old":
        values["action"] = "U"
      else:
        values["action"] = "A"
        
      self._parsed_data[-1].update(values)
      
    if event == "index":
      
      for k in ("tail", "head"):
        if values[k] == "0" * 40:
          del values[k]
      
      if self._parsed_data[-1].has_key("mode"):
        del values["mode"]
        
      self._parsed_data[-1].update(values)
    
    if event == "binary":
      self._parsed_data[-1]["format"] = values["format"].lower()
      
    if event == "chunk":

      if not values.has_key("left_len") or values["left_len"] == None:
        values["left_len"] = values["left_start"]

      if not values.has_key("right_len") or values["right_len"] == None:
        values["right_len"] = values["right_start"]

      for k in values.keys():
        values[k] = int(values[k])
      
      values["lines"] = []
        
      self._parsed_data[-1]["chunks"].append(values)
      
    if event == "line":
      # Check if new range has been specified
      if values["event"] not in "+- ":
        if self._event("chunk", self.CHUNK, values["event"]):
          if len(values["data"]) > 0:
            return self._event("line", self.LINE, values["data"])
        else:
          return False
          
      else:          
        values["data"] = values["data"].decode('utf-8', 'replace')
        self._parsed_data[-1]["chunks"][-1]["lines"].append(values)
        
    
    return True
    
  def __str__(self):
    
    return os.linesep.join(self._data)
    
  def _preparse(self):
    
    patterns = [
      ("commit", self.COMMIT),
      ("diff", self.DIFF),
      ("action", self.ACTION),
      ("index", self.INDEX),
      ("binary", self.BINARY),
      ("file", self.FILE),
      ("line", self.LINE),
    ]
    
    stack = list(patterns)
    event, pattern = stack[0]
    data = list(self._data)
    
    while data:
      
      first_event = event
      reset = False

      while stack and not self._event(event, pattern, data[0]):
        stack = stack[1:]
        
        if len(stack) == 0:
          reset = True
          stack = list(patterns)
        
        event, pattern = stack[0]
        
        if reset and first_event == event:
          print >> sys.stderr,  "error: Failed to parse line %s" % data[0]
          break
        
      data = data[1:]
  
      
class Commit(Record):
  
  TREE = re.compile(r"^tree (?P<index>[0-9a-fA-F]{40})$")
  PARENT = re.compile(r"^parent (?P<index>[0-9a-fA-F]{40})$")
  AUTHOR = re.compile(r"^author (?P<name>[^<]+) (<(?P<email>[^>]*)> )?(?P<epoch>[0-9]+) (?P<tz>.*)$")
  COMMITTER = re.compile(r"^committer (?P<name>[^<]+) (<(?P<email>[^>]*)> )?(?P<epoch>[0-9]+) (?P<tz>.*)$")
  BODY = re.compile(r"^$")
  LINE = re.compile(r"^    (?P<data>\w.*)$")
  SPLIT = re.compile(r"^    $")
  
  @property
  @cache
  def diff(self):
    return UnifiedDiff(self.provider.commit_diff(self.id))
    
  @property
  @cache
  def patch(self):
    return self.provider.commit_patch(self.id)
    
  def has_key(self, key):
    return Record.has_key(self, key) or \
           key in self.keys()

  def keys(self):
    return self.provider.commit_keys()
    
  @cache
  def parse_commit(self):
      
    o, e, v = self._provider.git("rev-list", "--parents", "--header", "--max-count=1", self.id)

    if v != 0:
      raise IOError(e)

    commit = {
      "tree" : [],
      "parent" : [],
      "author" : None,
      "committer" : None,
      "subject" : "",
      "body" : ""
      }

    patterns = [
      (self.TREE,     lambda index, **kwargs  : ("tree", index)),
      (self.PARENT,   lambda index, **kwargs  : ("parent", index)),
      (self.AUTHOR,   lambda **kwargs         : ("author", UserStamp(commit=self, **kwargs))),
      (self.COMMITTER, lambda **kwargs         : ("committer", UserStamp(commit=self, **kwargs))),
      (self.BODY,    lambda **kwargs         : (None, None)),
      (self.LINE,     lambda data, **kwargs   : ("subject", data)),
      (self.SPLIT,    lambda **kwargs         : (None, None)),
      (self.LINE,     lambda data, **kwargs   : ("body", data))
    ]

    p, f = patterns[0]

    lines = o.splitlines()[1:]

    while lines:
      data = lines[0]

      # Attempt to parse data, if parse fails pop parser and try next
      while patterns and not self.parse_data(p, f, data, commit):
        patterns = patterns[1:]
        if patterns:
          p, f = patterns[0]

      lines = lines[1:]

    return commit

  @property
  def remote_url(self):
    return self.provider._url
  
  @property
  def path(self):
    return self.provider._path
  
  def parse_data(self, pattern, func, data, commit):
    
    m = pattern.match(data)
    
    if m:
      target, data = func(**m.groupdict())
      
      if target in ("tree", "parent"):
        commit[target].append(data)
      elif target in ("author", "committer"):
        commit[target] = data
      elif target in ("subject", "body"):
        commit[target] += data + os.linesep
      return True
      
    return False
  
  @property
  @cache
  def labels(self):      
    return [Label(self._provider)[index] for index in self.provider.label_keys_by_commit(self.id)]
  
  @property
  def digest(self):
    return self.id

  @property
  def subject(self):
    return self.parse_commit()["subject"]
  
  @property
  def body(self):
    return self.parse_commit()["body"]
  
  @property
  def author(self):
    return self.parse_commit()["author"]

  @property
  def committer(self):
    return self.parse_commit()["committer"]
  
  def keys_by_date(self):
    return self.provider.commit_keys_by_date()
  
  @cache
  def values_by_date(self):
    return [self[k] for k in self.keys_by_date()]

  def keys_by_author(self, key):
    return self.provider.commit_keys_by_author(key)
  
  @cache
  def values_by_author(self, key):
    return [self[k] for k in self.keys_by_author(key)]

  def keys_by_committer(self, pattern):
    return self.provider.commit_keys_by_committer(key)

  @cache
  def values_by_committer(self, pattern):
    return [self[k] for k in self.keys_by_committer(key)]
  
  @property
  @cache
  def parents(self):
    return [ self[index] for index in self.parse_commit()["parent"] ]

class Label(Record):
  
  def has_key(self, key):

    return Record.has_key(self, key) or \
           key in self.keys()

  def keys(self):
    return self.provider.label_keys()

  @property
  @cache
  def patch(self):
    
    if self.tail and self.tail.id != self.head.id:
      f = open(self.provider.label_patch(len(self.commit_history_keys()), self.head.id))
      d = f.read()
      f.close()
    else:
      d = self.head.patch
      
    return d

  @property
  @cache
  def ticket(self):    
    return Ticket(self._provider)[self.provider.parse_labels()[self.id]["ticket"]]


  def commit_history_keys(self):
    return self.provider.parse_history(self.provider.parse_labels()[self.id]["head"], self.provider.parse_labels()[self.id]["tail"])

  @cache
  def commit_history_values(self):
    return [Commit(self.provider)[k] for k in self.commit_history_keys()]

  @property
  def head(self):
    return Commit(self.provider)[self.provider.parse_labels()[self.id]["head"]]

  @property
  def tail(self):
    return Commit(self.provider)[self.provider.parse_labels()[self.id]["tail"]]

  @property
  def name(self):
    return self.provider.parse_labels()[self.id]["name"]
    
class Ticket(Record):
  
  def has_key(self, key):

    return Record.has_key(self, key) or \
           key in self.keys()

  def keys(self):
    return self.provider.parse_tickets().keys()
    
  @property
  @cache
  def system(self):
    return System(self._provider)[self.provider.parse_tickets()[self.id]["system"]]

  def label_keys(self):
    return self.provider.parse_tickets()[self.id]["labels"]

  @property
  @cache
  def labels(self):
    return dict([(k, Label(self._provider)[k]) for k in self.label_keys()])

  @property
  def number(self):
    return self.provider.parse_tickets()[self.id]["number"]

  @property
  @cache
  def patch(self):      
    f = open(self.provider.ticket_patch(self.id))
    d = f.read()
    f.close()
      
    return d
      
class provider_type(type):

  def __init__(cls, classname, bases, classdict):
    super(provider_type, cls).__init__(classname, bases, classdict)
    setattr(cls, '__provides__', {})
      
class Provider(object):
  
  __metaclass__ = provider_type
  
  def provide(self, *classes):
    
    for cls in classes:
      if not issubclass(cls, Record):
        raise KeyError("Class '%s' is not a subclass of Record" % cls.__name__)
      
      if not self.__provides__.has_key(cls):
        self.__provides__[cls] = cls(self)
    
  def __getitem__(self, cls):
    return self.__provides__[cls]
    
class BugBox(Provider):

  def __init__(self, path):
    
    self._path = path

    #Make time stamp for syncing
    stamp =  os.path.join(self._path, STAMP)
    if not os.path.exists(stamp):
      f = file(stamp, 'a')
      
      try:
        os.utime(stamp, None)
      finally:
        f.close()

    self._paths = [
      os.path.join(self._path, "config"),
      stamp
    ]
    self._parse_systems = None
    self._modified = None
    
    o, e, v = self.git("rev-parse", "--git-dir")

    if v != 0:
      raise IOError(e)

    self._path = os.path.normpath(os.path.join(self._path, o.strip()))
    self._url  = self.parse_url()
    
    self.provide(System, Ticket, Label, Commit, Author)
    
  @property
  def modified(self):
    return max(*[os.stat(p)[stat.ST_MTIME] for p in self._paths])
    
  @property
  def synced(self):
    return self.modified == self._modified
  
  @log
  def sync(self):
    self._modified = self.modified
    
  @log
  def call(self, *args, **kwargs):
    p = subprocess.Popen(args, cwd=kwargs.get("cwd", os.getcwd()), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    o, e = p.communicate()

    if o: o = o.rstrip()
    if e: e = e.rstrip()

    return (o, e, p.returncode)

  def git(self, global_args=None, *args):

    cmd = ["git",]

    for arg in (global_args, args):
      if arg:
        if type(arg) in (list, tuple):
          cmd += list(arg)
        else:
          cmd.append(str(arg))

    return self.call(cwd=self._path, *cmd)
    
  def system_keys(self):
    return self.parse_systems().keys()
    
  @cache
  def parse_url(self):
    
    o, e, v = self.git("config", "bugbox.url")

    if v != 0 or len(o.strip()) == 0:
      return self._path
    else:
      return o.strip()
    
  @cache
  def parse_systems(self):

    o, e, v = self.git("var", "-l")

    if v != 0:
      raise IOError(e)

    var = dict([l.split("=") for l in o.splitlines()])

    systems = {}

    for k, v in var.items():

      if k.startswith("ticket"):
        parts = k.split(".")
        if len(parts) > 2:

          index = parts[1]
          attr  = parts[2]

          if not systems.has_key(index):
            systems[index] = {}

          systems[index][attr] = v

    return systems

  @cache  
  def parse_commits(self):

    label_refs = self.parse_labels().keys()

    commits = {}

    for ref in label_refs:
      o, e, v = self.git("rev-list", ref)

      if v != 0:
        raise IOError(o)

      values = [l.strip() for l in o.splitlines()]

      for v in values:
        if not commits.has_key(v):
          commits[v] = {
            "labels" : []
          }

        commits[v]["labels"].append(ref)

    return commits

  def commit_keys(self):
    return self.parse_commits().keys()
    
  def label_keys_by_commit(self, key):
    
    if self.parse_commits().has_key(key):
      return self.parse_commits()[key]["labels"]
      
    return []
    
  @cache
  def parse_commits_by_date(self):
    
    o, e, v = self.git("rev-list", "--date-order", "--all")

    if v != 0:
      raise IOError(e)

    return o.splitlines()

  def commit_keys_by_date(self):
    return self.parse_commits_by_date()
    
  @cache
  def parse_commit_keys_by_author(self, key):
    
    o, e, v = self.git("rev-list", "--date-order", "--author=%s" % key,"--all")

    if v != 0:
      raise IOError(e)

    return o.splitlines()
   
  def commit_keys_by_author(self, key):
    return self.parse_commit_keys_by_author(key)

  @cache
  def parse_commit_keys_by_committer(self, key):

    o, e, v = self.git("rev-list", "--date-order", "--committer=%s" % key,"--all")

    if v != 0:
      raise IOError(e)

    return o.splitlines()

  def commit_keys_by_committer(self, key):
    return self.parse_commit_keys_by_committer(key)

  @cache
  def parse_labels(self):
    
    tickets = self.parse_tickets()

    refs = {}

    for k, v in tickets.items():
      for lk, lv in v["labels"].items():
        refs[lk] = {
          "name" : lv["name"],
          "head" : lv["head"],
          "tail" : lv["tail"],
          "ticket" : k
        }

    return refs
    
  def label_keys(self):
    return self.parse_labels().keys()

  @cache
  def parse_tickets(self):

    o, e, v = self.git("for-each-ref", '--format=%(refname) %(objecttype) %(objectname)')

    if v != 0:
      raise IOError(o)

    refs = [l.strip().split(" ") for l in o.splitlines()]

    tickets = {}

    for r, t, h in refs:

      if t == "commit":
        index, values = self.parse_ref(r)

        if index:
          if not tickets.has_key(index):
            tickets[index] = {}
            tickets[index]["labels"] = {}

          tickets[index]["system"] = values["system"]
          tickets[index]["number"] = values["number"]
          tickets[index]["labels"][values["label_index"]] = {
            "name" : values["label"],
            "head" : h,
            "tail" : None}

    for r, t, h in refs:

      if t == "tag":
        index, values = self.parse_ref(r, tag=True)

        if tickets.has_key(index):
          tickets[index]["labels"][values["label_index"]]["tail"] = self.parse_tag(r)["head"]

    return tickets
    
  def set_tail(self, reference, revision):
    
    system, ticket, label = self.splitref(reference)
    
    if not system:
      raise AttributeError("Bad reference '%s'" % reference)
      return
      
    o, e, v = self.git("tag", "-f", "-a", "-m", "''", "%s/%s/%s/%s" % (TAIL, system, ticket, label), revision)
    
    if v != 0:
      raise IOError(o)
  
  @cache
  def has_ref(self, reference):

    o, e, v = self.git("show-ref", "--verify", "--quiet", reference)
    return v == 0

  @cache
  def parse_tag(self, reference):
      
    o, e, v = self.git("rev-list", '--max-count=1', reference)

    if v != 0:
      raise IOError(e)

    head = o.strip()

    return {
      "head" : o.strip(),
      "reference" : reference
    }
    
  def splitref(self, reference, mapped=False):
    m = REF_PATTERN.match(reference)
    
    if m:
      if mapped:
        return m.groupdict()
      else:
        group = m.groupdict()
        return (group['system'], group['number'], group['label'])
    else:
      if mapped:
        return None
      else:
        return (None, None, None)

  @cache
  def commit_diff(self, revision):
      
    o, e, v = self.git("diff-tree", "-r", "-p", "--full-index", revision)

    if v != 0:
      raise IOError(e)

    return o.splitlines()

  @cache
  def commit_patch(self, revision):

    o, e, v = self.git("diff-tree", "-r", "-p", "--binary", "--full-index", revision)

    if v != 0:
      raise IOError(e)

    return o

  @cache
  def ticket_patch(self, index):

    if self.tickets.has_key(index):

      z = tempfile.mkstemp()[-1]
      zf = ZipFile(z, mode="w")
      p = index.replace("/","_")
      t = self.tickets[index]

      for l in t.labels.values():
        l_len = len(l.commit_history_keys())

        if l_len > 1:
          l_path = self.label_patch(len(l.commit_history_keys()), l.head.id)
          lf = ZipFile(l_path, mode="r")
          
          for patch in lf.namelist():
            zf.writestr("%s/%s/%s" % (p, l.name, patch), lf.read(patch))

        else:
          zf.writestr("%s/%s/0001-%s.patch" % (p, l.name, l.head.id), self.commit_patch(l.head.id))
      
      zf.close()
      
      return z

  @cache
  def label_patch(self, length, revision):
      
    p = tempfile.mkdtemp()

    o, e, v = self.git("format-patch", "-o", p, "-k", "-%s" % length, revision)

    if v != 0:
      raise IOError(e)

    # TODO Hook into cherrypy on shutdown to remove temp files
    z = tempfile.mkstemp()[-1]
    zf = ZipFile(z, mode="w")

    for f in o.splitlines():
      fp = f.strip()
      zf.write(fp, os.path.basename(fp))

    zf.close()

    return z

  @cache
  def parse_history(self, head, tail):
    
    o, e, v = self.git("rev-list", '%s..%s' % (tail, head))

    if v != 0:
      raise IOError(e)

    return [l.strip() for l in o.splitlines()] + [tail,]
    
  @cache
  def parse_ref(self, reference, tag=False):

    m = REF_PATTERN.match(reference)

    systems = self.parse_systems().keys()

    if m:

      values = m.groupdict()

      if values["system"] in systems:
        key = "%(system)s/%(number)s" % values

        if values["label"] == None:
          values["label"] = "default"

        #values["label_index"] = key
        values["label_index"] = reference.replace("refs/tags/%s" % TAIL, "refs/heads")

        return (key, values)

      return  (None, None)
    
  @property
  def systems(self):
    return self[System]
    
  @property
  def tickets(self):
    return self[Ticket]

  @property
  def labels(self):
    return self[Label]

  @property
  def commits(self):
    return self[Commit]

  @property
  def authors(self):
    return self[Author]
    
  @property
  def path(self):
    return self._path
    
  @property
  def url(self):
    return self._url
