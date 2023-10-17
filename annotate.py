#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# MIT License
# 
# Copyright (c) 2023 Advanced Micro Devices, Inc. All Rights Reserved.
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

Standalone utility for creating user annotation labels in json format. Intened
for use in conjunction with companion Slurm data collector that looks for files of the
following form:

/tmp/omniwatch_${USER}_annotate.json
"""

import argparse
import time
import json
import os
timestamp = int(time.time())

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices = ['start','stop'],help="annotation mode", required=True)
parser.add_argument("--text", help="desired annotation", required=False)
args = parser.parse_args()

if args.mode == 'start' and args.text is None:
    parser.error("The --text option is required for \"start\" mode.")

filename="/tmp/omniwatch_" + os.getlogin() + "_annotate.json"

if args.mode == "start":
    data = {}
    data["annotation"] = args.text
    data["timestamp_secs"] = int(time.time())

    with open(filename,"w") as outfile:
        outfile.write(json.dumps(data,indent=4))
        outfile.write("\n")
else:
    if os.path.exists(filename):
        os.remove(filename) 
