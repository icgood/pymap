pymap
=====

Lightweight, asynchronous IMAP serving in Python.

[![Build Status](https://travis-ci.org/icgood/pymap.svg?branch=master)](https://travis-ci.org/icgood/pymap)
[![Coverage Status](https://coveralls.io/repos/icgood/pymap/badge.svg)](https://coveralls.io/r/icgood/pymap)
[![PyPI](https://img.shields.io/pypi/v/pymap.svg)](https://pypi.python.org/pypi/pymap)
[![PyPI](https://img.shields.io/pypi/pyversions/pymap.svg)](https://pypi.python.org/pypi/pymap)
[![PyPI](https://img.shields.io/pypi/l/pymap.svg)](https://pypi.python.org/pypi/pymap)

This project attempts to simplify the complexity of the [IMAP protocol][1] into
a set of clean Python APIs that can be implemented by pluggable backends.
Everything runs runs in an [asyncio][2] event loop.

There are two backend plugins included in the package, dict and maildir.

#### [API Documentation](http://icgood.github.io/pymap/)

### Table of Contents

* [Install and Usage](#install-and-usage)
  * [dict Plugin](#dict-plugin)
  * [maildir Plugin](#maildir-plugin)
* [Supported Extensions](#supported-extensions)
* [Development and Testing](#development-and-testing)
  * [Type Hinting](#type-hinting)

## Install and Usage

```bash
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

```bash
$ pymap --insecure-login --debug dict --demo-data
```

In another terminal, connect to port 1143 and run some commands:

```
* OK [CAPABILITY IMAP4rev1 STARTTLS AUTH=PLAIN AUTH=LOGIN AUTH=CRAM-MD5 BINARY UIDPLUS MULTIAPPEND IDLE APPENDLIMIT=1000000000] Server ready 163.1.168.192.in-addr.arpa
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
. list "" ""
. create "A New Folder"
. store * +FLAGS (\Deleted)
. expunge
```

### maildir Plugin

The maildir plugin uses on-disk storage for mail and metadata. For mail data,
it uses the eponymous [Maildir][3] format. However, since Maildir alone is not
enough for modern IMAP usage, it is extended with additional data as described
in Dovecot's [MailboxFormat/Maildir][4], with the intention of being fully
compatible.

For login, the plugin uses a simple formatted text file, e.g.:

```
john::s3cretp4ssword
sally:mail/data:sallypass
susan:/var/mail/susan:!@#$%^:*
```

The colon-delimited fields are the user ID, the mailbox path, and the password.
The mailbox path may be empty, relative, or absolute. An empty mailbox path
will use the user ID as a relative path.

Try out the maildir plugin:

```
$ pymap --insecure-login --debug maildir /path/to/users.txt
```

Once started, check out the dict plugin example above to connect and see it in
action. The biggest difference is, when stop and restart the pymap server, your
mail messages remain intact.

## Supported Extensions

In addition to [RFC 3501][1], pymap supports a number of IMAP extensions to
give clients easier and more powerful use.

#### [RFC 2177](https://tools.ietf.org/html/rfc2177)

Adds the `IDLE` capability and command, which lets clients wait (without
issuing commands) and receive mailbox updates as they happen without polling.

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

#### [RFC 7889 (partial)](https://tools.ietf.org/html/rfc7889)

Adds the `APPENDLIMIT=` capability, declaring the maximum message size a server
will accept from an `APPEND` command. Mailbox-specific limitations defined
by the RFC are not supported.

## Development and Testing

You will need to do some additional setup to develop and test plugins. First
off, I suggest activating a [virtualenv][5]. Then, install the test
requirements and a local link to the pymap package:

```
$ pip install -r test/requirements.txt
$ pip install -e .
```

Run the tests with py.test:

```
$ py.test
```

If you intend to create a pull request, you should make sure the full suite of
tests run by CI/CD is passing:

```
$ py.test --mypy --flake8 --cov=pymap
```

A py.test run executes both unit and integration tests. The integration tests
use mocked sockets to simulate the sending and receiving of commands and
responses, and are kept in the `test/server/` subdirectory.

### Type Hinting

This project makes heavy use of Python's [type hinting][6] system, with the
intention of a clean run of [mypy][7]:

```
mypy pymap
```

No code contribution will be accepted unless it makes every effort to use type
hinting to the extent possible and common in the rest of the codebase. There is
no need to attempt `--strict` mode.

[1]: https://tools.ietf.org/html/rfc3501
[2]: https://docs.python.org/3/library/asyncio.html
[3]: https://en.wikipedia.org/wiki/Maildir
[4]: https://wiki.dovecot.org/MailboxFormat/Maildir
[5]: https://virtualenv.pypa.io/en/latest/
[6]: https://www.python.org/dev/peps/pep-0484/
[7]: http://mypy-lang.org/
