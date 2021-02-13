
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Optional

import msgpack
from aioredis import Redis

from pymap.message import BaseMessage, BaseLoadedMessage
from pymap.mime import MessageContent, MessageHeader, MessageBody
from pymap.parsing.specials import Flag, ObjectId, FetchRequirement

from .keys import NamespaceKeys, ContentKeys

__all__ = ['Message', 'LoadedMessage']


class Message(BaseMessage):

    __slots__ = ['_redis', '_ns_keys']

    def __init__(self, uid: int, internal_date: datetime,
                 permanent_flags: Iterable[Flag], *, expunged: bool = False,
                 email_id: ObjectId = None, thread_id: ObjectId = None,
                 redis: Redis = None, ns_keys: NamespaceKeys = None) -> None:
        super().__init__(uid, internal_date, permanent_flags,
                         expunged=expunged, email_id=email_id,
                         thread_id=thread_id)
        self._redis = redis
        self._ns_keys = ns_keys

    async def _load_full(self, redis: Redis, ct_keys: ContentKeys) \
            -> MessageContent:
        literal, full_json_raw = await redis.hmget(
            ct_keys.data, b'full', b'full-json')
        if literal is None or full_json_raw is None:
            raise ValueError(f'Missing message content: {self.email_id}')
        full_json = msgpack.unpackb(full_json_raw, raw=False)
        return MessageContent.from_json(literal, full_json)

    async def _load_header(self, redis: Redis, ct_keys: ContentKeys) \
            -> MessageContent:
        literal, header_json_raw = await redis.hmget(
            ct_keys.data, b'header', b'header-json')
        if literal is None or header_json_raw is None:
            raise ValueError(f'Missing message header: {self.email_id}')
        header_json = msgpack.unpackb(header_json_raw, raw=False)
        header = MessageHeader.from_json(literal, header_json)
        body = MessageBody.empty()
        return MessageContent(literal, header, body)

    async def load_content(self, requirement: FetchRequirement) \
            -> LoadedMessage:
        redis = self._redis
        ns_keys = self._ns_keys
        if redis is None or ns_keys is None:
            return LoadedMessage(self, requirement, None)
        ct_keys = ContentKeys(ns_keys, self.email_id)
        content: Optional[MessageContent] = None
        if requirement & FetchRequirement.BODY:
            content = await self._load_full(redis, ct_keys)
        elif requirement & FetchRequirement.HEADER:
            content = await self._load_header(redis, ct_keys)
        return LoadedMessage(self, requirement, content)

    @classmethod
    def copy_expunged(cls, msg: Message) -> Message:
        return cls(msg.uid, msg.internal_date, msg.permanent_flags,
                   expunged=True, email_id=msg.email_id,
                   thread_id=msg.thread_id, redis=msg._redis,
                   ns_keys=msg._ns_keys)


class LoadedMessage(BaseLoadedMessage):
    pass
