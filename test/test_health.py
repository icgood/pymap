
import unittest
from collections.abc import Callable
from typing import ParamSpec, TypeVar
from unittest.mock import MagicMock

from pymap.health import HealthStatus

_T = TypeVar('_T')
_P = ParamSpec('_P')


class TestHealthStatus(unittest.TestCase):

    def setUp(self) -> None:
        self._callback = MagicMock()

    def _check_no_call(self, func: Callable[_P, _T],
                       *args: _P.args, **kwargs: _P.kwargs) -> _T:
        ret = func(*args, **kwargs)
        self._callback.assert_not_called()
        self._callback.reset_mock()
        return ret

    def _check_call(self, healthy: bool, func: Callable[_P, _T],
                    *args: _P.args, **kwargs: _P.kwargs) -> _T:
        ret = func(*args, **kwargs)
        self._callback.assert_called_once_with(healthy)
        self._callback.reset_mock()
        return ret

    def test_name(self) -> None:
        status = HealthStatus(name='foo')
        self.assertEqual('foo', status.name)
        child1 = status.new_dependency(name='bar')
        self.assertEqual('foo.bar', child1.name)
        child2 = status.new_dependency(name='baz')
        self.assertEqual('foo.baz', child2.name)
        child3 = child1.new_dependency(name='oof')
        self.assertEqual('foo.bar.oof', child3.name)

    def test_set(self) -> None:
        status = HealthStatus()
        self.assertTrue(status.healthy)
        status = HealthStatus(False)
        self.assertFalse(status.healthy)
        status.set(True)
        self.assertTrue(status.healthy)
        status.set_unhealthy()
        self.assertFalse(status.healthy)
        status.set_healthy()
        self.assertTrue(status.healthy)

    def test_callback(self) -> None:
        status = HealthStatus()
        self._check_call(True, status.register, self._callback)
        self._check_call(False, status.set_unhealthy)
        self._check_no_call(status.set_unhealthy)
        self._check_call(True, status.set_healthy)
        self._check_no_call(status.set_healthy)

    def test_add_dependency(self) -> None:
        parent = HealthStatus()
        self._check_call(True, parent.register, self._callback)
        deps = [self._check_no_call(parent.new_dependency, True),
                self._check_call(False, parent.new_dependency, False)]
        self._check_no_call(deps[0].set_healthy)
        self._check_call(True, deps[1].set_healthy)
        self._check_call(False, parent.set_unhealthy)
        self._check_call(True, parent.set_healthy)
        self._check_call(False, deps[0].set_unhealthy)
        self._check_no_call(deps[1].set_unhealthy)
        self._check_no_call(deps.pop)
        self._check_call(True, deps.clear)
