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

"""SLURM data collector

Implements a prometheus info metric to track SLURM job-related info.  The
default resulting metric is named "slurmjob_info{}" and is always published.  An
optional "slurmjob_annotations{}" metric can be published to provide
user-provided annotation timestamps.
"""

import sys
import utils
import json
import logging
import os
import platform
from collector_base import Collector
from prometheus_client import Gauge, generate_latest, CollectorRegistry

class SlurmJob(Collector):
    def __init__(self):
        logging.debug("Initializing SlurmJob data collector")
        self.__prefix = "slurmjob_"

        # setup slurm binary path
        command = utils.resolvePath("squeue", "SLURM_PATH")
        # command-line flags for use with squeue to obtained desired metrics
        hostname = platform.node().split(".", 1)[0]
        flags = (
            "-w "
            + hostname
            + " -h  --Format=JobID::,UserName::,Partition::,NumNodes::,BatchFlag"
        )
        # cache query command with options
        self.__squeue_query = [command] + flags.split()

        logging.debug("sqeueue_exec = %s" % self.__squeue_query)

        self.__SLURMmetrics = {}

    def registerMetrics(self):
        """Register metrics of interest"""

        # alternate approach - define an info metric
        # (https://ypereirareis.github.io/blog/2020/02/21/how-to-join-prometheus-metrics-by-label-with-promql/)
        labels = ["jobid", "user", "partition", "nodes", "batchflag"]
        self.__SLURMmetrics["info"] = Gauge(
            self.__prefix + "info", "SLURM job id", labels
        )

        # metric to support user annotations
        self.__SLURMmetrics["annotations"] = Gauge(
            self.__prefix + "annotations", "User job annotations", ["marker", "jobid"]
        )

        for metric in self.__SLURMmetrics:
            logging.debug("--> Registered SLURM metric = %s" % metric)

    def updateMetrics(self):
        data = utils.runShellCommand(self.__squeue_query)

        self.__SLURMmetrics["info"].clear()
        self.__SLURMmetrics["annotations"].clear()

        # Case when SLURM job is allocated
        if data.stdout.strip():
            # query output format:
            # JOBID,USER,PARTITION,NODES,CPUS
            results = data.stdout.strip().split(":")

            self.__SLURMmetrics["info"].clear()
            self.__SLURMmetrics["info"].labels(
                jobid=results[0],
                user=results[1],
                partition=results[2],
                nodes=results[3],
                batchflag=results[4],
            ).set(1)

            # Check for user supplied annotations
            userFile = "/tmp/omniwatch_%s_annotate.json" % results[1]
            if os.path.isfile(userFile):
                with open(userFile, "r") as file:
                    data = json.load(file)

                self.__SLURMmetrics["annotations"].labels(
                    marker=data["annotation"],
                    jobid=results[0],
                ).set(data["timestamp_secs"])

        # Case when no job detected
        else:
            self.__SLURMmetrics["info"].labels(
                jobid="", user="", partition="", nodes="", batchflag=""
            ).set(1)

        return