pymap
=====

Lightweight, asynchronous IMAP serving in Python.

[![build](https://github.com/icgood/pymap/actions/workflows/python-check.yml/badge.svg)](https://github.com/icgood/pymap/actions/workflows/python-check.yml)
[![PyPI](https://img.shields.io/pypi/v/pymap.svg)](https://pypi.python.org/pypi/pymap)
[![PyPI](https://img.shields.io/pypi/pyversions/pymap.svg)](https://pypi.python.org/pypi/pymap)
![platforms](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20windows-blueviolet)
[![PyPI](https://img.shields.io/pypi/l/pymap.svg)](https://pypi.python.org/pypi/pymap)

This project attempts to simplify the complexity of the [IMAP protocol][1] into
a set of clean Python APIs that can be implemented by pluggable backends.
Everything runs in an [asyncio][2] event loop.

#### [API Documentation](https://icgood.github.io/pymap/)

#### [Docker Image](https://github.com/icgood/pymap/pkgs/container/pymap)

### Table of Contents

* [Install and Usage](#install-and-usage)
  * [dict Plugin](#dict-plugin)
  * [maildir Plugin](#maildir-plugin)
    * [maildir Quick Start](#maildir-quick-start)
  * [redis Plugin](#redis-plugin)
    * [redis Quick Start](#redis-quick-start)
* [Admin Tool](#admin-tool)
  * [Configuring an MTA](#configuring-an-mta)
* [Supported Extensions](#supported-extensions)
* [Development and Testing](#development-and-testing)
  * [Type Hinting](#type-hinting)

## Install and Usage

```console
$ pip install pymap
$ pymap --help
$ pymap dict --help
$ pymap maildir --help
```

### dict Plugin

The dict plugin uses in-memory dictionary objects to store mail and metadata.
While the server is running, all concurrent and future connections will see the
same data, including added and removed messages, but no changes will persist if
the server is restarted.

You can try out the dict plugin with demo data:

```console
$ pymap --port 1143 --debug dict --demo-data
```

In another terminal, connect to port 1143 and run some commands:

```
* OK [CAPABILITY IMAP4rev1 STARTTLS AUTH=PLAIN AUTH=LOGIN AUTH=CRAM-MD5 BINARY UIDPLUS MULTIAPPEND IDLE APPENDLIMIT=1000000000] Server ready my.hostname.local
. login demouser demopass
. OK Authentication successful.
. select INBOX
* OK [PERMANENTFLAGS (\Answered \Deleted \Draft \Flagged \Seen)] Flags permitted.
* FLAGS (\Answered \Deleted \Draft \Flagged \Recent \Seen)
* 4 EXISTS
* 1 RECENT
* OK [UIDNEXT 105] Predicted next UID.
* OK [UIDVALIDITY 4097774359] UIDs valid.
* OK [UNSEEN 4] First unseen message.
. OK [READ-WRITE] Selected mailbox.
. logout
* BYE Logging out.
. OK Logout successful.
```

Here are some other commands to try:

```
. uid fetch 1:* all
. list "" *
. create "A New Folder"
. store * +FLAGS (\Deleted)
. expunge
```

Add new messages using the append command:

```
. append INBOX (\Flagged) {38+}
From: user@example.com

test message!

```

### maildir Plugin

The maildir plugin uses on-disk storage for mail and metadata. For mail data,
it uses the eponymous [Maildir][3] format. However, since Maildir alone is not
enough for modern IMAP usage, it is extended with additional data as described
in Dovecot's [MailboxFormat/Maildir][4], with the intention of being fully
compatible.

For login, the plugin uses files compatible with the [`/etc/passwd`][14],
[`/etc/shadow`][15], and [`/etc/group`][16] formats. By default, they are
prefixed with `pymap-etc-` and placed inside the configured base directory to
avoid conflicting with the corresponding system files.

#### maildir Quick Start

Start the pymap server pointing to a base directory, e.g.:

```console
$ pymap --port 1143 --debug maildir ~/maildir/
```

In another terminal, use [pymap-admin](#admin-tool) to create a user to login
with:

```console
$ pymap-admin set-user demouser
# Type in a password at the prompt, e.g. "demopass"
```

If you already have a maildir folder that you could like to reuse, you can
re-assign your user's `mailbox_path`:

```console
$ pymap-admin set-user --param mailbox_path=/path/to/mailbox demouser
# Re-type or change the password
```

You are now ready to login to IMAP on port 1143 using your favorite mail
client.

### redis Plugin

The redis plugin uses the [Redis][8] data structure store for mail and
metadata. It requires [redis-py][9] and will not appear in the plugins list
without it.

```console
$ pip install 'pymap[redis]'
$ pymap redis --help
```

Keys are composed of a heirarchy of prefixes separated by `/`. For example, the
key containing the flags of a message might be:

```
/ns/eacb1cf1558741d0b5419b3f838882f5/mbx/Fdaddd3075d7b42e78a7edb1d87ee5800/msg/9173/flags
```

In this example, the `eacb1cf1558741d0b5419b3f838882f5` and
`Fdaddd3075d7b42e78a7edb1d87ee5800` prefixes are randomly generated IDs acting
as the namespaces for the login user and mailbox, respectively, and the message
has UID `9173`.

#### redis Quick Start

Start the pymap server pointing to a local redis server, or use `--address` to
connect to a remote redis, e.g.:

```console
$ pymap --port 1143 --debug redis  # --address redis://my.redis
```

In another terminal, use [pymap-admin](#admin-tool) to create a user to login
with:

```console
$ pymap-admin set-user demouser
# Type in a password at the prompt, e.g. "demopass"
```

You are now ready to login to IMAP on port 1143 using your favorite mail
client.

## Admin Tool

With optional dependencies, the pymap server will also open a [gRPC][11]
service providing administrative operations for the running server.

```console
$ pip install 'pymap[admin,macaroon]'
```

The admin service can create, update, and delete users, deliver new messages,
check credentials, and provide health checks.

The [pymap-admin][10] CLI tool simplifies interacting with the admin service.
It can also be installed standalone to interact with remote pymap servers:

```console
$ pip install pymap-admin
$ pymap-admin --help
```

### Configuring an MTA

The admin tool can be used as a ["local delivery agent"][12] for an MTA with
the `append` sub-command. For example, in postfix you might use:

```
mailbox_command = /some/where/pymap-admin --from "$SENDER" "$USER"
```

This setup may be combined with [remote authentication][13] to keep a clean
separation between your MTA and pymap.

## Supported Extensions

In addition to [RFC 3501][1], pymap supports a number of IMAP extensions to
give clients easier and more powerful use.

#### [RFC 2177](https://tools.ietf.org/html/rfc2177)

Adds the `IDLE` capability and command, which lets clients wait (without
issuing commands) and receive mailbox updates as they happen without polling.

#### [RFC 2180](https://tools.ietf.org/html/rfc2180)

Defines some conventions for handling multi-access in scenarios such as
`EXPUNGE` and mailbox deletion.

#### [RFC 2971](https://tools.ietf.org/html/rfc2971)

Adds the `ID` capability and command, which lets clients send and receive
arbitrary information for "statistical" purposes and bug reports.

#### [RFC 3502](https://tools.ietf.org/html/rfc3502)

Adds the `MULTIAPPEND` capability, allowing multiple messages to be atomically
appended to a mailbox with a single `APPEND` command.

#### [RFC 3516](https://tools.ietf.org/html/rfc3516)

Adds the `BINARY` extension, providing better support for the encoding and
transfer of binary data.

#### [RFC 4315](https://tools.ietf.org/html/rfc4315)

Adds the `UIDPLUS` capability, which adds the `UID EXPUNGE` command and defines
the `APPENDUID` and `COPYUID` giving clients more insight into the messages
added to a mailbox.

#### [RFC 4466](https://tools.ietf.org/html/rfc4466)

No additional functionality by itself, but allows pymap to be extended easily
and more robustly handle bad client implementations.

#### [RFC 5530](https://tools.ietf.org/html/rfc5530)

Adds additional IMAP response codes that can help tell an IMAP client why a
command failed.

#### [RFC 7889 (partial)](https://tools.ietf.org/html/rfc7889)

Adds the `APPENDLIMIT=` capability, declaring the maximum message size a server
will accept from an `APPEND` command. Mailbox-specific limitations defined
by the RFC are not supported.

#### [RFC 8474](https://tools.ietf.org/html/rfc8474)

Adds the `OBJECTID` capability, assigning unique IDs to mailboxes, messages,
and threads to improve client caching and display.

## Development and Testing

You will need to do some additional setup to develop and test plugins. Install
[Hatch][5] to use the CLI examples below.

Run all tests and linters:

```console
$ hatch run check
```

### Type Hinting

This project makes heavy use of Python's [type hinting][6] system, with the
intention of a clean run of [mypy][7].

No code contribution will be accepted unless it makes every effort to use type
hinting to the extent possible and common in the rest of the codebase.

[1]: https://tools.ietf.org/html/rfc3501
[2]: https://docs.python.org/3/library/asyncio.html
[3]: https://en.wikipedia.org/wiki/Maildir
[4]: https://wiki.dovecot.org/MailboxFormat/Maildir
[5]: https://hatch.pypa.io/latest/install/
[6]: https://www.python.org/dev/peps/pep-0484/
[7]: http://mypy-lang.org/
[8]: https://redis.io/
[9]: https://github.com/redis/redis-py
[10]: https://github.com/icgood/pymap-admin
[11]: https://grpc.io/
[12]: https://www.postfix.org/postconf.5.html#mailbox_command
[13]: https://github.com/icgood/pymap-admin#authentication
[14]: https://linux.die.net/man/5/passwd
[15]: https://linux.die.net/man/5/shadow
[16]: https://linux.die.net/man/5/group
