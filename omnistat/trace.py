#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2024 Advanced Micro Devices, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -------------------------------------------------------------------------------

import time
import zmq


class OmnistatTrace:
    """
    Tracer to annotate coarse-grained application regions. Each trace can be
    used to track a single process; multiple processes connect to the same
    path/socket, but require different IDs.

    Attributes
    ----------
    trace_id : str
        Trace identifier. In scale-out scenarios, this can be the rank of the
        current process.
    path : str
        Path to the unix domain socket used to communicate with the collector.

    Methods
    -------
    start_span(label):
        Starts a region/span.
    end_span(label):
        Ends region/span.
    """

    def __init__(self, trace_id="0", path="/tmp/omnistat_trace"):
        self._trace_id = trace_id
        self._zmq_context = zmq.Context()
        self._zmq_socket = self._zmq_context.socket(zmq.PUSH)
        self._zmq_socket.connect(f"ipc://{path}")

    def start_span(self, label):
        time_ms = time.time_ns() // 1_000_000
        msg = ["start", time_ms, self._trace_id, label]
        self._zmq_socket.send_json(msg)

    def end_span(self, label):
        time_ms = time.time_ns() // 1_000_000
        msg = ["end", time_ms, self._trace_id, label]
        self._zmq_socket.send_json(msg)
