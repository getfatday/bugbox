
def run(*tests):
  import os, unittest, sys
  
  suite = unittest.TestSuite()
  loader = unittest.defaultTestLoader
  runner = unittest.TextTestRunner(sys.stdout, verbosity=1)
  
  if len(tests) == 0:
    tests = None
  
  for root, dirs, files, in os.walk(os.path.dirname(__file__)):
    
    package = os.path.split(root)[1]
    
    for f in files:
      if f.startswith("test_") and f.endswith(".py"):
        name = os.path.splitext(f)[0]
        path = ("%s.%s" % (package, name))
        
        if not tests or path in tests:
          m = getattr(__import__(path), name)
          suite.addTest(loader.loadTestsFromModule(m))
    
    break
    
  runner.run(suite)
  sys.exit()

if __name__ == '__main__':
  run(*sys.argv[1:])