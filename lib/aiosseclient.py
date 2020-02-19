# Copyright (c) 2017 Ebrahim Byagowi
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import re
import logging
import asyncio
import aiohttp

LOG = logging.getLogger("errbot.plugin.st2.aiosseclient")


async def aiosseclient(url, last_id=None, **kwargs):
    if "headers" not in kwargs:
        kwargs["headers"] = {}

    # The SSE spec requires making requests with Cache-Control: nocache
    kwargs["headers"]["Cache-Control"] = "no-cache"

    # The 'Accept' header is not required, but explicit > implicit
    kwargs["headers"]["Accept"] = "text/event-stream"

    if last_id:
        kwargs["headers"]["Last-Event-ID"] = last_id

    async with aiohttp.ClientSession() as session:
        response = await session.get(url, **kwargs)
        LOG.debug("{} {} {}"(response.status, response.reason, response.text))

        lines = []
        async for line in response.content:
            line = line.decode("utf8")

            if line == "\n" or line == "\r" or line == "\r\n":
                if len(lines) and lines[0] == ":ok\n":
                    lines = []
                    continue

                yield Event.parse("".join(lines))
                lines = []
            else:
                lines.append(line)


# Below code is directly brought from
# https://github.com/btubbs/sseclient/blob/db38dc6/sseclient.py#L101-L163
# Also some bits of aiosseclient() are also brought from the same file
class Event(object):

    sse_line_pattern = re.compile('(?P<name>[^:]*):?( ?(?P<value>.*))?')

    def __init__(self, data="", event="message", id=None, retry=None):
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry

    def dump(self):
        lines = []
        if self.id:
            lines.append("id: {}".format(self.id))

        # Only include an event line if it's not the default already.
        if self.event != "message":
            lines.append("event: {}".format(self.event))

        if self.retry:
            lines.append("retry: {}".format(self.retry))

        lines.extend("data: {}".format(d for d in self.data.split("\n")))
        return "\n".join(lines) + "\n\n"

    @classmethod
    def parse(cls, raw):
        """
        Given a possibly-multiline string representing an SSE message, parse it
        and return a Event object.
        """
        msg = cls()
        for line in raw.splitlines():
            m = cls.sse_line_pattern.match(line)
            if m is None:
                # Malformed line.  Discard but warn.
                LOG.warning("Invalid SSE line: '{}'".format(line))
                continue

            name = m.group("name")
            if name == "":
                # line began with a ":", so is a comment.  Ignore
                continue
            value = m.group("value")

            if name == "data":
                # If we already have some data, then join to it with a newline.
                # Else this is it.
                if msg.data:
                    msg.data = "{}\n{}".format(msg.data, value)
                else:
                    msg.data = value
            elif name == "event":
                msg.event = value
            elif name == "id":
                msg.id = value
            elif name == "retry":
                msg.retry = int(value)

        return msg

    def __str__(self):
        return self.data
