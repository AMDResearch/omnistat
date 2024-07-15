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
# Query resource manager environment and save job data to local file. Output
# intended for use by collector_rms.py collector to demarcate user jobs.
#
# Usage:rms_env.py [output_file]
#
# Default path for output_file: /tmp/omni_rmsjobinfo
# -------------------------------------------------------------------------------

import json
import os
import subprocess
import sys


def main():
    jobData = {}
    jobFile = "/tmp/omni_rmsjobinfo"

    if len(sys.argv) > 1:
        jobFile = sys.argv[1]

    if "SLURM_JOB_ID" in os.environ:
        jobData["SLURM_JOB_ID"] = os.getenv("SLURM_JOB_ID")
        jobData["SLURM_JOB_USER"] = os.getenv("SLURM_JOB_USER")
        jobData["SLURM_JOB_PARTITION"] = os.getenv("SLURM_JOB_PARTITION")
        jobData["SLURM_JOB_NUM_NODES"] = os.getenv("SLURM_JOB_NUM_NODES")
        if "SLURM_PTY_PORT" in os.environ:
            jobData["SLURM_JOB_BATCHMODE"] = 0
        else:
            jobData["SLURM_JOB_BATCHMODE"] = 1

    elif "FLUX_URI" in os.environ:
        command = ["flux", "-p", "jobs", "-n", "--format={id.f58},{username},{queue},{nnodes}"]
        try:
            results = subprocess.run(command, capture_output=True, text=True, timeout=5.0)
        except:
            print("ERROR: Unable to query flux for job information")
            sys.exit(0)

        fluxdata = results.stdout.strip().split(",")
        jobData["SLURM_JOB_ID"] = fluxdata[0]
        jobData["SLURM_JOB_USER"] = fluxdata[1]
        jobData["SLURM_JOB_PARTITION"] = fluxdata[2]
        jobData["SLURM_JOB_NUM_NODES"] = fluxdata[3]
        jobData["SLURM_JOB_BATCHMODE"] = 1  # marking all jobs as batch jobs to start

    else:
        print("ERROR: SLURM settings not visible in current environment. Verify running in active job")
        sys.exit(1)

    # save to file
    json.dump(jobData, open(jobFile, "w"), indent=4)


if __name__ == "__main__":
    main()
