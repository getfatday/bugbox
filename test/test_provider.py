import unittest
from bugbox import Provider
from bugbox import Record

class ObjectCase(unittest.TestCase):

  __cls__ = Provider

  def setUp(self):
    self.obj = self.__cls__()
    self.name = self.__cls__.__name__
    
  def tearDown(self):
    pass
    
  def testProvides(self):
    
    self.obj.provides(Record)
    obj = self.__cls__()
    
    self.assertTrue(obj.__provides__.has_key(Record), "Object instance does not contain Record class")
    