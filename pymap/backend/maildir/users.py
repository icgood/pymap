
from __future__ import annotations

import os.path
import re
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, fields
from typing import ClassVar, Generic, IO, Protocol, Self, TypeVar

from .io import FileWriteable

__all__ = ['UserRecord', 'PasswordRecord', 'GroupRecord',
           'UsersFile', 'PasswordsFile', 'GroupsFile', 'TokensFile']

_RecordT = TypeVar('_RecordT', bound='_Record')


class _Record(Protocol):

    name: str

    @classmethod
    @abstractmethod
    def get_fields(cls) -> Sequence[str]:
        ...


@dataclass(frozen=True)
class UserRecord(_Record):
    """Encapsulates a single user line in the passwd file.

    See Also:
        `passwd(5) <https://linux.die.net/man/5/passwd>`_

    """

    name: str
    password: str = ''
    uid: str = ''
    gid: str = ''
    comment: str = ''
    home_dir: str = ''
    shell: str = ''

    @classmethod
    def get_fields(cls) -> Sequence[str]:
        return [field.name for field in fields(cls)]

    def copy(self, *, name: str | None = None,
             password: str | None = None,
             uid: str | None = None,
             home_dir: str | None = None) -> UserRecord:
        return UserRecord(
            name=name if name is not None else self.name,
            password=password if password is not None else self.password,
            uid=uid if uid is not None else self.uid,
            gid=self.gid,
            comment=self.comment,
            home_dir=home_dir if home_dir is not None else self.home_dir,
            shell=self.shell)


@dataclass(frozen=True)
class PasswordRecord(_Record):
    """Encapsulates a single user line in the shadow file.

    See Also:
        `shadow(5) <https://linux.die.net/man/5/shadow>`_

    """

    name: str
    password: str
    last_change_date: str = ''
    min_password_age: str = ''
    max_password_age: str = ''
    password_warning_period: str = ''
    password_inactivity_period: str = ''
    account_expiration_date: str = ''
    reserved: str = ''

    @classmethod
    def get_fields(cls) -> Sequence[str]:
        return [field.name for field in fields(cls)]

    def copy(self, *, name: str | None = None,
             password: str | None = None,
             last_change_date: str | None = None) -> PasswordRecord:
        return PasswordRecord(
            name=name if name is not None else self.name,
            password=password if password is not None else self.password,
            last_change_date=self.last_change_date,
            min_password_age=self.min_password_age,
            max_password_age=self.max_password_age,
            password_warning_period=self.password_warning_period,
            password_inactivity_period=self.password_inactivity_period,
            account_expiration_date=self.account_expiration_date,
            reserved=self.reserved)


@dataclass(frozen=True)
class GroupRecord(_Record):
    """Encapsulates a single group line in the group file.

    See Also:
        `group(5) <https://linux.die.net/man/5/group>`_

    """

    name: str
    password: str = ''
    gid: str = ''
    users_list: str = ''

    @classmethod
    def get_fields(cls) -> Sequence[str]:
        return [field.name for field in fields(cls)]

    @property
    def users(self) -> frozenset[str]:
        return self.parse_users_list(self.users_list)

    def copy(self, *, name: str | None = None,
             password: str | None = None,
             users_list: str | None = None) -> GroupRecord:
        return GroupRecord(
            name=name if name is not None else self.name,
            password=password if password is not None else self.password,
            gid=self.gid,
            users_list=(users_list if users_list is not None
                        else self.users_list))

    def add_users(self, users: Collection[str]) -> GroupRecord:
        all_users = self.users | set(users)
        new_users_list = self.build_users_list(all_users)
        return self.copy(users_list=new_users_list)

    @classmethod
    def parse_users_list(cls, users_list: str) -> frozenset[str]:
        return frozenset(users_list.split(',') if users_list else [])

    @classmethod
    def build_users_list(cls, users: Collection[str]) -> str:
        return ','.join(sorted(users))


class _ColonSeparatedValuesFile(FileWriteable, Generic[_RecordT]):

    _pattern = re.compile(r'(?<!\\):')  # split on non-escaped colons

    FILE_NAME: ClassVar[str]

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._records: dict[str, _RecordT] = {}

    @property
    def empty(self) -> bool:
        return not self._records

    @classmethod
    @abstractmethod
    def get_record_type(cls) -> type[_RecordT]:
        ...

    @classmethod
    def get_file(cls, path: str) -> str:
        return os.path.join(path, cls.FILE_NAME)

    def has(self, name: str) -> bool:
        return name in self._records

    def get(self, name: str) -> _RecordT:
        return self._records[name]

    def get_all(self) -> Collection[_RecordT]:
        return self._records.values()

    def set(self, record: _RecordT) -> None:
        self._records[record.name] = record
        self.touch()

    def remove(self, name: str) -> None:
        del self._records[name]
        self.touch()

    @classmethod
    def get_default(cls, path: str) -> Self:
        return cls(path)

    @classmethod
    def open(cls, path: str, fp: IO[str]) -> Self:
        return cls(path)

    def read(self, fp: IO[str]) -> None:
        record_type = self.get_record_type()
        pattern = self._pattern
        for line in fp:
            fields = (part.replace('\\:', ':')
                      for part in pattern.split(line.rstrip('\r\n')))
            record = record_type(*fields)
            self.set(record)

    def write(self, fp: IO[str]) -> None:
        record_type = self.get_record_type()
        fields = record_type.get_fields()
        for record in self._records.values():
            line = ':'.join(getattr(record, field).replace(':', '\\:')
                            for field in fields)
            fp.write(line)
            fp.write('\r\n')


class _PasswdFile(_ColonSeparatedValuesFile[UserRecord]):

    @classmethod
    def get_record_type(cls) -> type[UserRecord]:
        return UserRecord


class _ShadowFile(_ColonSeparatedValuesFile[PasswordRecord]):

    @classmethod
    def get_record_type(cls) -> type[PasswordRecord]:
        return PasswordRecord


class _GroupFile(_ColonSeparatedValuesFile[GroupRecord]):

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._by_user: dict[str, set[GroupRecord]] = defaultdict(set)

    @classmethod
    def get_record_type(cls) -> type[GroupRecord]:
        return GroupRecord

    def _unlink_users(self, name: str) -> None:
        if name in self._records:
            record = self._records[name]
            for user in record.users:
                self._by_user[user].discard(record)

    def _link_users(self, record: GroupRecord) -> None:
        for user in record.users:
            self._by_user[user].add(record)

    def set(self, record: GroupRecord) -> None:
        self._unlink_users(record.name)
        super().set(record)
        self._link_users(record)

    def remove(self, name: str) -> None:
        self._unlink_users(name)
        super().remove(name)

    def merge(self, groups: Iterable[GroupRecord]) -> None:
        """Merge the *groups* into the file. If a group does not exist, it is
        added. Any missing users will be added to each existing group.

        Args:
            groups: The groups to merge.

        Raises:
            ValueError: A new group was incompatible with an existing group.

        """
        for group in groups:
            name = group.name
            existing = self._records.get(name)
            if existing is None:
                self.set(group)
            else:
                updated_group = group.add_users(existing.users)
                updated_existing = existing.add_users(group.users)
                if updated_group != updated_existing:
                    raise ValueError(group)
                self.set(updated_group)

    def get_user(self, user: str) -> frozenset[GroupRecord]:
        """Look up a user name and get the set of groups to which it belongs.

        Args:
            user: The user name.

        """
        if user in self._by_user:  # do not want defaultdict to create it
            return frozenset(self._by_user[user])
        else:
            return frozenset()

    def remove_user(self, user: str) -> None:
        """Remove a user from any groups to which it belongs.

        Args:
            user: The user name.

        """
        if user in self._by_user:
            groups = frozenset(self._by_user[user])
            for group in groups:
                new_users = group.users - {user}
                if new_users:
                    new_users_list = GroupRecord.build_users_list(new_users)
                    new_group = group.copy(users_list=new_users_list)
                    super().set(new_group)
                else:
                    super().remove(group.name)


class UsersFile(_PasswdFile):
    """Reads and writes a file using the
    `passwd file format <https://linux.die.net/man/5/passwd>`_. The home
    directory field in the user record will be the path (absolute or relative
    to the base directory) to the user's maildir.

    """

    #: The users file name.
    FILE_NAME: ClassVar[str] = 'pymap-etc-passwd'

    @classmethod
    def build_record(cls, name: str, mailbox_path: str) -> UserRecord:
        return UserRecord(name=name,
                          password='x',  # noqa: S106
                          home_dir=mailbox_path)

    @classmethod
    def get_lock(cls, path: str) -> str | None:
        return f'{cls.get_file(path)}.lock'


class PasswordsFile(_ShadowFile):
    """Reads and writes a file using the
    `passwd file format <https://linux.die.net/man/5/passwd>`_. Similar to the
    ``/etc/shadow`` file on a Linux system, this file contains the password
    representation and may have stricter file permissions.

    """

    #: The passwords file name.
    FILE_NAME: ClassVar[str] = 'pymap-etc-shadow'

    @classmethod
    def build_record(cls, name: str, password: str) -> PasswordRecord:
        return PasswordRecord(name=name, password=password)


class GroupsFile(_GroupFile):
    """Reads and writes a file using the
    `group file format <https://linux.die.net/man/5/group>`_. The name field
    in each record is the role name, and the users list are the users that have
    been assigned that role.

    """

    #: The roles file name.
    FILE_NAME: ClassVar[str] = 'pymap-etc-group'

    @classmethod
    def build_record(cls, name: str, user: str) -> GroupRecord:
        return GroupRecord(name=name,
                           password='x',  # noqa: S106
                           users_list=user)


class TokensFile(_GroupFile):
    """Reads and writes a file using the
    `group file format <https://linux.die.net/man/5/group>`_. The name field
    in each record is the token identifier, the password field is the private
    key, and the users list contains the user or users it is valid for.

    """

    #: The roles file name.
    FILE_NAME: ClassVar[str] = 'pymap-tokens'

    @classmethod
    def build_record(cls, identifier: str, key: bytes, authcid: str) \
            -> GroupRecord:
        return GroupRecord(name=identifier,
                           password=key.hex(),  # noqa: S106
                           users_list=authcid)

    def set(self, record: GroupRecord) -> None:
        if record.name in self._records:
            raise ValueError('Token identifier already exists.')
        super().set(record)
