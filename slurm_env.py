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

# Query relevant SLURM env variables and save to local file. Intended
# for use with SLURM data collector on systems where direct API query
# is slow/problematic.

import json
import os
import sys

jobData = {}

if "SLURM_JOB_ID" in os.environ:
    jobData["SLURM_JOB_ID"] = os.getenv("SLURM_JOB_ID")
    jobData["SLURM_JOB_USER"] = os.getenv("SLURM_JOB_USER")
    jobData["SLURM_JOB_PARTITION"] = os.getenv("SLURM_JOB_PARTITION")
    jobData["SLURM_JOB_NUM_NODES"] = os.getenv("SLURM_JOB_NUM_NODES")
    if "SLURM_PTY_PORT" in os.environ:
        jobData["SLURM_JOB_BATCHMODE"] = 0
    else:
        jobData["SLURM_JOB_BATCHMODE"] = 1

    json.dump(jobData,open("/tmp/omniwatch_slurm_job_assigned","w"),indent=4)

else:
    print("ERROR: SLURM settings not visible in current environment. Verify running in active job")
    sys.exit(1)
    
