
import unittest
from typing import Final
from unittest.mock import create_autospec, Mock

from pymap.cluster import ListenCallback, ClusterMetadata


class _Member:

    def __init__(self, name: str) -> None:
        self.name: Final = name
        self.metadata: Final = {'name': name.encode('ascii')}

    def __hash__(self) -> int:
        return hash(self.name)


class TestClusterMetadata(unittest.TestCase):

    def test_local(self) -> None:
        metadata = ClusterMetadata()
        self.assertEqual(0, len(metadata.local))
        data = {'one': b'1', 'two': b'2', 'three': b'3'}
        metadata.local.update(data)
        self.assertEqual(data, metadata.local)
        del metadata.local['two']
        self.assertEqual(b'1', metadata.local['one'])
        self.assertNotIn('two', metadata.local)
        self.assertEqual(b'3', metadata.local['three'])

    def test_listen(self) -> None:
        callback = create_autospec(ListenCallback)
        arg = Mock()
        metadata = ClusterMetadata()
        metadata.local['one'] = b'1'
        metadata.listen(callback, arg)
        callback.assert_called_with(arg, {'one': b'1'})
        metadata.local['two'] = b'2'
        callback.assert_called_with(arg, {'one': b'1', 'two': b'2'})
        del metadata.local['two']
        callback.assert_called_with(arg, {'one': b'1'})
        metadata.local['one'] = b'one'
        callback.assert_called_with(arg, {'one': b'one'})
        metadata.local
        callback.reset_mock()
        del arg
        metadata.local['three'] = b'3'
        callback.assert_not_called()
        self.assertEqual({'one': b'one', 'three': b'3'}, metadata.local)

    def test_remote(self) -> None:
        member1 = _Member('one')
        member2 = _Member('two')
        metadata = ClusterMetadata([member1, member2])
        self.assertEqual({member1, member2}, set(metadata))
        self.assertEqual(2, len(metadata))
        self.assertIn(member1, metadata)
        self.assertIn(member2, metadata)
        self.assertEqual(1, len(metadata.remote))
        self.assertEqual({'name': {member1: b'one', member2: b'two'}},
                         metadata.remote)
        del member2
        self.assertEqual({'name': {member1: b'one'}}, metadata.remote)
        metadata.discard(member1)
        self.assertEqual({'name': {}}, metadata.remote)

    def test_get_all(self) -> None:
        member1 = _Member('one')
        member2 = _Member('two')
        metadata = ClusterMetadata([member1, member2])
        metadata.local['name'] = b'three'
        self.assertEqual({b'one', b'two', b'three'}, metadata.get_all('name'))
