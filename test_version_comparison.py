from writer import Version
import unittest

class TestVersionMethods(unittest.TestCase):
    def test_bad_formatting(self):        
        self.assertRaises(ValueError, Version, '0.0.')
        self.assertRaises(ValueError, Version, '0.0')
        
    def test_lt(self):
        v1 = Version('1.0.0')
        v2 = Version('2.0.0')
        self.assertTrue(v1 < v2)
        
        v1 = Version('1.2.0')
        v2 = Version('1.4.0')
        self.assertTrue(v1 < v2)
        
        v1 = Version('1.2.4')
        v2 = Version('1.2.6')
        self.assertTrue(v1 < v2)
        
        v1 = Version('1.2.6')
        v2 = Version('1.3.4')
        self.assertTrue(v1 < v2)
        
        v1 = Version('1.10.6')
        v2 = Version('2.3.4')
        self.assertTrue(v1 < v2)
        
    def test_eq(self):
        v1 = Version('2.23.5')
        v2 = Version('2.23.5')
        self.assertTrue(v1 == v2)
        self.assertTrue(v1 <= v2)
        self.assertTrue(v2 == v1)
        self.assertTrue(v2 >= v1)
        
        v2 = Version('2.23.6')
        
        self.assertTrue(v1 != v2)
        
    def test_gt(self):
        v1 = Version('1.0.0')
        v2 = Version('2.0.0')
        self.assertTrue(v2 > v1)
        
        v1 = Version('1.2.0')
        v2 = Version('1.4.0')
        self.assertTrue(v2 > v1)
        
        v1 = Version('1.2.4')
        v2 = Version('1.2.6')
        self.assertTrue(v2 > v1)
        
        v1 = Version('1.2.6')
        v2 = Version('1.3.4')
        self.assertTrue(v2 > v1)
        
        v1 = Version('1.10.6')
        v2 = Version('2.3.4')
        self.assertTrue(v2 > v1)
        
if __name__ == '__main__':
    unittest.main()