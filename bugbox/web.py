#! /usr/bin/env python

import cherrypy, os, subprocess, re, sys, hashlib, types
from bugbox import BugBox
from genshi.core import Stream
from genshi.output import encode, get_serializer
from genshi.template import Context, TemplateLoader

def debug():
  import pdb
  pdb.set_trace()

class Template(object):
  
  def __init__(self):
    self.loader = None

  def namespace(self, k, v):
    
    if k == 'dir':
      self.loader = TemplateLoader(v, auto_reload=True)

  def url(self, path=""):
    return cherrypy.url(path=path, relative='server')

  def output(self, filename, method='html', encoding='utf-8', **options):
      """Decorator for exposed methods to specify what template the should use
      for rendering, and which serialization method and options should be
      applied.
      """
      def decorate(func):
          def wrapper(*args, **kwargs):
              #debug()
              cherrypy.thread_data.template = self.loader.load(filename)
              opt = options.copy()
              if method == 'html':
                  opt.setdefault('doctype', 'html')
              serializer = get_serializer(method, **opt)
              stream = func(*args, **kwargs)
              if not isinstance(stream, Stream):
                  return stream
              return encode(serializer(stream), method=serializer,
                            encoding=encoding)
          return wrapper
      return decorate

  def render(self, *args, **kwargs):
      """Function to render the given data to the template specified via the
      ``@output`` decorator.
      """
      if args:
          assert len(args) == 1, \
              'Expected exactly one argument, but got %r' % (args,)
          template = self.loader.load(args[0])
      else:
          template = cherrypy.thread_data.template
        
      ua = cherrypy.request.headers.get('user-agent').lower()
    
      if "chrome" in ua:
        browser = "chrome"
      elif "webkit" in ua:
        browser = "safari"
      elif "opera" in ua:
        browser = "opera"
      elif "msie" in ua:
        browser = "msie"
      elif "mozilla" in ua:
        browser = "mozilla"
      else:
        browser = "unknown"
    
      ctxt = Context(url=self.url, request=cherrypy.request, response=cherrypy.response, browser=browser)
      ctxt.push(kwargs)
      return template.generate(ctxt)

template = Template()
cherrypy.config.namespaces['template'] = template.namespace

class BugBoxApp(object):
  
  config = {
      '/css' : {
        'tools.staticdir.on' : True,
        'tools.staticdir.dir' : "shared/css"
      },
      '/img' : {
        'tools.staticdir.on' : True,
        'tools.staticdir.dir' : "shared/img"
      }
    }
  
  
  def __init__(self):
    self._bugbox = None
    self._app = None
    self._repository = None
  
  @property
  def bugbox(self):
    
    if self._bugbox == None and self._repository:
      self._bugbox = BugBox(self._repository)
      
    return self._bugbox
    
  @property
  def base(self):
    return self._base
  
  @cherrypy.expose
  @template.output('index.html')
  def index(self):
    #debug()
    return template.render(systems=self.bugbox.systems.values(), tickets=self.bugbox.tickets.values())
  
  @cherrypy.expose
  @template.output('tickets.html')
  def tickets(self, system=None, ticket=None, label=None):
    
    if system and self.bugbox.systems.has_key(system):
      
      ticket = "%s/%s" % (system, ticket)
      system = self.bugbox.systems[system]
      
      if ticket and system.tickets.has_key(ticket):
        
        label = "refs/heads/%s/%s" % (ticket, label)
        
        if label and system.tickets[ticket].labels.has_key(label):
          return template.render('label.html', system=system, ticket=system.tickets[ticket], label=system.tickets[ticket].labels[label])
        
        return template.render('ticket.html', system=system, ticket=system.tickets[ticket])
        
      tickets = system.tickets.values()
    else:
      tickets = self.bugbox.tickets.values()
        
    return template.render(system=system, tickets=tickets)

  @cherrypy.expose
  @template.output('authors.html')
  def authors(self, email=None):
    
    if email and self.bugbox.authors.has_key(email):
      return template.render('author.html', author=self.bugbox.authors[email])
      
    return template.render(authors=self.bugbox.authors.values())

  @cherrypy.expose
  @template.output('commits.html')
  def commits(self, digest=None):

    if digest and self.bugbox.commits.has_key(digest):
      return template.render('commit.html', commit=self.bugbox.commits[digest])

    return template.render(commits=self.bugbox.commits.values_by_date()[0:25])

  @cherrypy.expose
  def rss(self, id=None):
    tmpl = loader.load('rss.xml')
    stream = tmpl.generate(tickets=self.bugbox.tickets.values()) 
    return stream.render('xml')
    
  def namespace(self, k, v):
      
    if k == 'dir':
      
      path = os.path.abspath(os.path.expanduser(v))
      
      if not os.path.isdir(path):
        raise IOError("Dir '%s' does not exist" % path)
        
      self._repository = path

root = BugBoxApp()
cherrypy.config.namespaces['bugbox'] = root.namespace

def root_dir(path):
  
  path = os.path.abspath(path)
  
  if not os.path.exists(path):
    raise IOError("Directory or file '%s' does not exist" % path)
    
  if os.path.isfile(path):
    path = os.path.dirname(path)
    
  if os.path.isdir(os.path.join(path, "shared")):
    return path
    
  path, d = os.path.split(path)
  
  if len(d) == 0:
    raise IOError("Shared directory can not be found")
    
  return root_dir(path)
    
rd = root_dir(__file__)
    
cherrypy.config.update({
  'tools.staticdir.root': rd ,
  'template.dir': os.path.join(rd, 'shared/templates')
})

def start(path="/"):
  cherrypy.quickstart(root, path)
    
if __name__ == '__main__':
  start(root)
    