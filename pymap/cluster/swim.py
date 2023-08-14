
from __future__ import annotations

import asyncio
import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Mapping
from contextlib import AsyncExitStack

from pymap.context import cluster_metadata
from pymap.health import HealthStatus
from pymap.interfaces.backend import ServiceInterface
from swimprotocol.config import ConfigError, TransientConfigError
from swimprotocol.members import Member, Members
from swimprotocol.status import Status
from swimprotocol.transport import load_transport
from swimprotocol.worker import Worker


__all__ = ['transport_type', 'SwimService']

_log = logging.getLogger(__name__)

#: The :class:`~swimprotocol.transport.Transport` implementation.
transport_type = load_transport()


class SwimService(ServiceInterface):  # pragma: no cover
    """A pymap service implemented using `swim-protocol
    <https://icgood.github.io/swim-protocol/>`_ to establish a cluster of pymap
    instances.

    """

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        transport_type.config_type.add_arguments(parser, prefix='--swim-')

    async def _health_update(self, member: Member, members: Members,
                             health: HealthStatus) -> None:
        if members.get_status(Status.OFFLINE):
            health.set_unhealthy()
        else:
            health.set_healthy()

    async def _remote_update(self, member: Member) -> None:
        if member.status & Status.AVAILABLE \
                and member.metadata is not Member.METADATA_UNKNOWN:
            cluster_metadata.get().add(member)
        else:
            cluster_metadata.get().discard(member)

    def _local_update(self, members: Members,
                      metadata: Mapping[str, bytes]) -> None:
        members.update(members.local, new_metadata=metadata)

    async def _start(self, args: Namespace, stack: AsyncExitStack) -> None:
        while True:
            try:
                config = transport_type.config_type.from_args(
                    args, ping_interval=10.0,
                    ping_timeout=1.0,
                    suspect_timeout=300.0,
                    sync_interval=30.0)
            except TransientConfigError as exc:
                _log.debug('SWIM configuration failure: %s', exc)
                await asyncio.sleep(exc.wait_hint)
            except ConfigError:
                return  # do not run SWIM if not configured properly
            else:
                break
        _log.debug('SWIM configuration: %r %r',
                   config.local_name, config.peers)
        health = HealthStatus(False, name='swim')

        members = Members(config)
        worker = Worker(config, members)
        transport = transport_type(config, worker)
        cluster_metadata.get().listen(self._local_update, members)
        await stack.enter_async_context(transport)
        await stack.enter_async_context(worker)
        await stack.enter_async_context(
            members.listener.on_notify(self._remote_update))
        await stack.enter_async_context(
            members.listener.on_notify(self._health_update, members, health))

    async def start(self, stack: AsyncExitStack) -> None:
        args = self.config.args
        task = asyncio.create_task(self._start(args, stack))
        stack.callback(task.cancel)
