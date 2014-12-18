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

import asyncio

from pymap.parsing.command import BadCommand, Command
from pymap.parsing import RequiresContinuation


@asyncio.coroutine
def client_connected(reader, writer):
    done = False
    while not done:
        line = yield from reader.readline()
        if reader.at_eof():
            break
        conts = []
        while not done:
            try:
                ret, _ = Command.parse(line, continuations=conts.copy())
            except RequiresContinuation as req:
                writer.write(b'+ ' + req.message + b'\r\n')
                yield from writer.drain()
                extra_literal = yield from reader.readexactly(req.literal_length)
                extra_line = yield from reader.readline()
                if reader.at_eof():
                    done = True
                    break
                conts.append(extra_literal + extra_line)
            except BadCommand as bad:
                writer.write(bytes(bad) + b'\r\n')
                yield from writer.drain()
                break
            else:
                writer.write(ret.tag + b' ' + ret.command + b' OK\r\n')
                yield from writer.drain()
                break


def main():
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(client_connected, port=1143, loop=loop)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
