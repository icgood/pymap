# Copyright (c) 2014 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

"""IMAP server with pluggable Python backends."""

import asyncio
from argparse import ArgumentParser
from functools import partial

from pkg_resources import iter_entry_points

from .core import __version__
from .server import IMAPServer


def _load_backends():
    return {entry_point.name: entry_point.load() for entry_point in
            iter_entry_points('pymap.backend')}


def main():
    backends = _load_backends()

    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--port', action='store', type=int, default=1143)
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)
    subparsers = parser.add_subparsers(dest='backend',
                                       help='Which pymap backend to use.')
    for mod in backends.values():
        mod.add_subparser(subparsers)
    args = parser.parse_args()

    try:
        backend = backends[args.backend]
    except KeyError:
        parser.error('Expected backend name.')
        return

    callback = partial(IMAPServer.callback, backend.init(args))
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(callback, port=args.port, loop=loop)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
