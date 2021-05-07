
from __future__ import annotations

import asyncio
from argparse import ArgumentParser
from collections.abc import Mapping
from contextlib import AsyncExitStack

from pymap.context import cluster_metadata
from pymap.interfaces.backend import ServiceInterface
from swimprotocol.config import ConfigError
from swimprotocol.members import Member, Members
from swimprotocol.status import Status
from swimprotocol.transport import load_transport


__all__ = ['transport_type', 'SwimService']

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

    async def _remote_update(self, member: Member) -> None:
        if member.status & Status.AVAILABLE \
                and member.metadata is not Member.METADATA_UNKNOWN:
            cluster_metadata.get().add(member)
        else:
            cluster_metadata.get().discard(member)

    def _local_update(self, members: Members,
                      metadata: Mapping[str, bytes]) -> None:
        members.update(members.local, new_metadata=metadata)

    async def start(self, stack: AsyncExitStack) -> None:
        args = self.config.args
        try:
            config = transport_type.config_type.from_args(args)
        except ConfigError:
            return  # do not run SWIM if not configured properly
        transport = transport_type(config)
        members = Members(config)
        cluster_metadata.get().listen(self._local_update, members)
        stack.enter_context(members.listener.on_notify(self._remote_update))
        worker = await stack.enter_async_context(transport.enter(members))
        task = asyncio.create_task(worker.run())
        stack.callback(task.cancel)
