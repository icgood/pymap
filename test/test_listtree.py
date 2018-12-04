
import unittest

from pymap.listtree import ListEntry, ListTree


class TestListEntry(unittest.TestCase):

    def test_attributes(self) -> None:
        self.assertEqual([b'HasNoChildren'],
                         ListEntry('', True, None, False).attributes)
        self.assertEqual([b'HasChildren'],
                         ListEntry('', True, None, True).attributes)
        self.assertEqual([b'Noselect', b'HasChildren'],
                         ListEntry('', False, None, True).attributes)
        self.assertEqual([b'HasNoChildren', b'Marked'],
                         ListEntry('', True, True, False).attributes)
        self.assertEqual([b'HasNoChildren', b'Unmarked'],
                         ListEntry('', True, False, False).attributes)


class TestListTree(unittest.TestCase):

    def setUp(self) -> None:
        tree = ListTree('/')
        tree.update('INBOX',
                    'Sent',
                    'Trash',
                    'Important/One',
                    'Important/Two',
                    'To Do',
                    'To Do/Quickly')
        tree.set_marked('To Do', marked=True)
        tree.set_marked('To Do/Quickly', unmarked=True)
        self.tree = tree

    def test_list(self) -> None:
        self.assertEqual([ListEntry('INBOX', True, None, False),
                          ListEntry('Sent', True, None, False),
                          ListEntry('Trash', True, None, False),
                          ListEntry('Important', False, None, True),
                          ListEntry('Important/One', True, None, False),
                          ListEntry('Important/Two', True, None, False),
                          ListEntry('To Do', True, True, True),
                          ListEntry('To Do/Quickly', True, False, False)],
                         list(self.tree.list()))

    def test_list_matching(self) -> None:
        self.assertEqual([ListEntry('Important', False, None, True),
                          ListEntry('Important/One', True, None, False),
                          ListEntry('Important/Two', True, None, False)],
                         list(self.tree.list_matching('Important', '*')))
