
import unittest

from pymap.parsing.specials.sequenceset import MaxValue, SequenceSet


class TestSequenceSet(unittest.TestCase):

    def test_contains(self) -> None:
        set1 = SequenceSet([12])
        self.assertIn(12, set1.flatten(100))
        self.assertNotIn(13, set1.flatten(100))
        self.assertNotIn(12, set1.flatten(10))
        set2 = SequenceSet([MaxValue()])
        self.assertIn(100, set2.flatten(100))
        self.assertNotIn(21, set2.flatten(100))
        self.assertNotIn(21, set2.flatten(20))
        set3 = SequenceSet([(5, 10)])
        self.assertIn(7, set3.flatten(100))
        self.assertNotIn(7, set3.flatten(6))
        self.assertNotIn(11, set3.flatten(100))
        self.assertNotIn(4, set3.flatten(100))
        set4 = SequenceSet([(MaxValue(), 10)])
        self.assertIn(11, set4.flatten(100))
        self.assertNotIn(9, set4.flatten(100))
        self.assertNotIn(101, set4.flatten(100))
        set5 = SequenceSet([(10, MaxValue())])
        self.assertIn(11, set5.flatten(100))
        self.assertNotIn(9, set5.flatten(100))
        self.assertNotIn(101, set5.flatten(100))
        set6 = SequenceSet([(MaxValue(), MaxValue())])
        self.assertIn(12, set6.flatten(12))
        self.assertNotIn(13, set6.flatten(12))
        self.assertNotIn(11, set6.flatten(12))

    def test_set(self) -> None:
        set1 = SequenceSet([12])
        self.assertEqual([12], list(set1.flatten(100)))
        set2 = SequenceSet([MaxValue()])
        self.assertEqual([100], list(set2.flatten(100)))
        set3 = SequenceSet([(MaxValue(), MaxValue())])
        self.assertEqual([100], list(set3.flatten(100)))
        set4 = SequenceSet([(5, 10)])
        self.assertEqual(list(range(5, 11)), list(set4.flatten(100)))
        set5 = SequenceSet([(MaxValue(), 10)])
        self.assertEqual(list(range(10, 101)), list(set5.flatten(100)))
        set6 = SequenceSet([(10, MaxValue())])
        self.assertEqual(list(range(10, 101)), list(set6.flatten(100)))
        set7 = SequenceSet([(1, 2), (4, 5), (7, 8)])
        self.assertEqual([1, 2, 4, 5, 7, 8], list(set7.flatten(100)))
        set8 = SequenceSet([(3, 5), (4, 6)])
        self.assertEqual([3, 4, 5, 6], list(set8.flatten(100)))
        set9 = SequenceSet([(MaxValue(), 50), (60, 10)])
        self.assertEqual(list(range(10, 101)), list(set9.flatten(100)))
        set10 = SequenceSet([(10, 1000)])
        self.assertEqual(list(range(10, 101)), list(set10.flatten(100)))
        set11 = SequenceSet([(1000, 1000)])
        self.assertEqual([], list(set11.flatten(100)))

    def test_bytes(self) -> None:
        seq = SequenceSet([12, MaxValue(), (1, MaxValue())])
        self.assertEqual(b'12,*,1:*', bytes(seq))
        self.assertEqual(b'12,*,1:*', bytes(seq))

    def test_build(self) -> None:
        seq = SequenceSet.build([1])
        self.assertEqual(b'1', bytes(seq))
        seq = SequenceSet.build([1, 1, 1])
        self.assertEqual(b'1', bytes(seq))
        seq = SequenceSet.build([1, 2, 3, 4, 5])
        self.assertEqual(b'1:5', bytes(seq))
        seq = SequenceSet.build([1, 2, 4, 5])
        self.assertEqual(b'1:2,4:5', bytes(seq))
        seq = SequenceSet.build([1, 2, 4, 6])
        self.assertEqual(b'1:2,4,6', bytes(seq))
        seq = SequenceSet.build([1, 3, 5])
        self.assertEqual(b'1,3,5', bytes(seq))
        seq = SequenceSet.build([1, 2, 3, 4, 5])
