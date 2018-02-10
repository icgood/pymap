
import unittest

from pymap.parsing.specials import SequenceSet


class TestSequenceSet(unittest.TestCase):

    def test_contains(self):
        set1 = SequenceSet([12])
        self.assertTrue(set1.contains(12, 100))
        self.assertFalse(set1.contains(13, 100))
        self.assertFalse(set1.contains(12, 10))
        set2 = SequenceSet(['*'])
        self.assertTrue(set2.contains(100, 100))
        self.assertFalse(set2.contains(21, 100))
        self.assertFalse(set2.contains(21, 20))
        set3 = SequenceSet([(5, 10)])
        self.assertTrue(set3.contains(7, 100))
        self.assertFalse(set3.contains(7, 6))
        self.assertFalse(set3.contains(11, 100))
        self.assertFalse(set3.contains(4, 100))
        set4 = SequenceSet([('*', 10)])
        self.assertTrue(set4.contains(11, 100))
        self.assertFalse(set4.contains(9, 100))
        self.assertFalse(set4.contains(101, 100))
        set5 = SequenceSet([(10, '*')])
        self.assertTrue(set5.contains(11, 100))
        self.assertFalse(set5.contains(9, 100))
        self.assertFalse(set5.contains(101, 100))
        set6 = SequenceSet([('*', '*')])
        self.assertTrue(set6.contains(12, 12))
        self.assertFalse(set6.contains(13, 12))
        self.assertFalse(set6.contains(11, 12))

    def test_iter(self):
        set1 = SequenceSet([12])
        self.assertEqual([12], list(set1.iter(100)))
        set2 = SequenceSet(['*'])
        self.assertEqual([100], list(set2.iter(100)))
        set3 = SequenceSet([('*', '*')])
        self.assertEqual([100], list(set3.iter(100)))
        set4 = SequenceSet([(5, 10)])
        self.assertEqual(list(range(5, 11)), list(set4.iter(100)))
        set5 = SequenceSet([('*', 10)])
        self.assertEqual(list(range(10, 101)), list(set5.iter(100)))
        set6 = SequenceSet([(10, '*')])
        self.assertEqual(list(range(10, 101)), list(set6.iter(100)))
        set7 = SequenceSet([(1, 2), (4, 5), (7, 8)])
        self.assertEqual([1, 2, 4, 5, 7, 8], list(set7.iter(100)))
        set8 = SequenceSet([(3, 5), (4, 6)])
        self.assertEqual([3, 4, 5, 6], list(set8.iter(100)))
        set9 = SequenceSet([('*', 50), (60, 10)])
        self.assertEqual(list(range(10, 101)), list(set9.iter(100)))
        set10 = SequenceSet([(10, 1000)])
        self.assertEqual(list(range(10, 101)), list(set10.iter(100)))
        set11 = SequenceSet([(1000, 1000)])
        self.assertEqual([], list(set11.iter(100)))

    def test_bytes(self):
        seq = SequenceSet([12, '*', (1, '*')])
        self.assertEqual(b'12,*,1:*', bytes(seq))
        self.assertEqual(b'12,*,1:*', bytes(seq))
