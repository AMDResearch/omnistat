#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2023 - 2024 Advanced Micro Devices, Inc. All Rights Reserved.
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

"""annotate.py

Standalone utility for creating user annotations that relies on Omnistat
traces. Intended for use in conjunction with companion Slurm data collector
that looks for trace messages in a specific path/socket.

For more detailed application-level traces of Python applications, import
omnistat's trace module.
"""

import argparse
import time
import json
import os

from omnistat import trace

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["start", "stop"], help="annotation mode", required=True)
    parser.add_argument("--text", help="desired annotation", required=True)
    args = parser.parse_args()

    trace = trace.OmnistatTrace(trace_id="annotations")

    if args.mode == "start":
        trace.start_span(args.text)
    else:
        trace.end_span(args.text)


if __name__ == "__main__":
    main()
