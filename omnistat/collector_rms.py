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

"""Resource manager data collector

Implements a prometheus info metric to track job-related info.  The
default resulting metric is named "rmsjob_info{}" and is always published.  An
optional "rmsjob_annotations{}" metric can be published to provide
user-provided annotation timestamps.
"""

import sys
import json
import logging
import os
import platform

from prometheus_client import Gauge, CollectorRegistry

import omnistat.utils as utils
from omnistat.collector_base import Collector


class RMSJob(Collector):
    def __init__(self, userMode=False, annotations=False, jobDetection=None):
        logging.debug("Initializing resource manager job data collector")
        self.__prefix = "rmsjob_"
        self.__userMode = userMode
        self.__annotationsEnabled = annotations
        self.__RMSMetrics = {}
        self.__rmsJobInfo = []
        self.__lastAnnotationLabel = None
        self.__rmsJobMode = jobDetection["mode"]
        self.__rmsJobFile = jobDetection["file"]

        # setup squeue binary path to query slurm to determine node ownership
        command = utils.resolvePath("squeue", "SLURM_PATH")
        # command-line flags for use with squeue to obtained desired metrics
        hostname = platform.node().split(".", 1)[0]
        flags = "-w " + hostname + " -h  --Format=JobID::,UserName::,Partition::,NumNodes::,BatchFlag"
        # cache query command with options
        self.__squeue_query = [command] + flags.split()
        logging.debug("sqeueue_exec = %s" % self.__squeue_query)

        # cache current slurm job in user mode profiling - assumption is that it does not change
        if self.__userMode is True:
            # read from file if available
            jobFile = self.__rmsJobFile
            if os.path.isfile(jobFile):
                with open(jobFile, "r") as f:
                    self.__rmsJobInfo = json.load(f)
                logging.info("--> usermode jobinfo (from file): %s" % self.__rmsJobInfo)

            else:
                # no job file data available: query slurm directly
                # note: a longer timeout is provided since we only query once and some systems have slow
                # slurm response times
                logging.info("User mode collector enabled for SLURM, querying job info once at startup...")
                self.__rmsJobInfo = self.querySlurmJob(timeout=15, exit_on_error=True, mode="squeue")
                logging.info("--> usermode jobinfo (from slurm query): %s" % self.__rmsJobInfo)

        else:
            if self.__rmsJobMode == "file-based":
                logging.info(
                    "collector_rms: reading job information from prolog/epilog derived file (%s)"
                    % self.__rmsJobFile
                )
            elif self.__rmsJobMode == "squeue":
                logging.info("collector_rms: will poll slurm periodicaly with squeue")
            else:
                logging.error("Unsupported slurm job data collection mode")

    def querySlurmJob(self, timeout=1, exit_on_error=False, mode="squeue"):
        """
        Query SLURM and return job info for local host.
        Supports two query modes: squeue call and read from file.

        Returns dictionary containing job id, user, partition, # of nodes, and batchmode flag
        """

        results = {}
        if mode == "squeue":
            data = utils.runShellCommand(self.__squeue_query, timeout=timeout, exit_on_error=exit_on_error)
            # squeue query output format: JOBID:USER:PARTITION:NUM_NODES:BATCHFLAG
            if data.stdout.strip():
                data = data.stdout.strip().split(":")
                keys = [
                    "SLURM_JOB_ID",
                    "SLURM_JOB_USER",
                    "SLURM_JOB_PARTITION",
                    "SLURM_JOB_NUM_NODES",
                    "SLURM_JOB_BATCHMODE",
                ]
                results = dict(zip(keys, data))
        elif mode == "file-based":
            jobFileExists = os.path.isfile(self.__rmsJobFile)
            if jobFileExists:
                with open(self.__rmsJobFile, "r") as file:
                    results = json.load(file)
        return results

    def registerMetrics(self):
        """Register metrics of interest"""

        # alternate approach - define an info metric
        # (https://ypereirareis.github.io/blog/2020/02/21/how-to-join-prometheus-metrics-by-label-with-promql/)
        labels = ["jobid", "user", "partition", "nodes", "batchflag"]
        self.__RMSMetrics["info"] = Gauge(self.__prefix + "info", "SLURM job id", labels)

        # metric to support user annotations
        self.__RMSMetrics["annotations"] = Gauge(
            self.__prefix + "annotations", "User job annotations", ["marker", "jobid"]
        )

        for metric in self.__RMSMetrics:
            logging.debug("--> Registered RMS metric = %s" % metric)

    def updateMetrics(self):
        self.__RMSMetrics["info"].clear()
        self.__RMSMetrics["annotations"].clear()
        jobEnabled = False

        results = None

        if self.__userMode is True:
            results = self.__rmsJobInfo
            jobEnabled = True
        else:
            results = self.querySlurmJob(mode=self.__rmsJobMode)
            if results:
                jobEnabled = True

        # Case when SLURM job is allocated
        if jobEnabled:
            self.__RMSMetrics["info"].labels(
                jobid=results["SLURM_JOB_ID"],
                user=results["SLURM_JOB_USER"],
                partition=results["SLURM_JOB_PARTITION"],
                nodes=results["SLURM_JOB_NUM_NODES"],
                batchflag=results["SLURM_JOB_BATCHMODE"],
            ).set(1)

            # Check for user supplied annotations
            if self.__annotationsEnabled:
                userFile = "/tmp/omnistat_%s_annotate.json" % results["SLURM_JOB_USER"]

                userFileExists = os.path.isfile(userFile)
                if userFileExists:
                    with open(userFile, "r") as file:
                        data = json.load(file)

                # Reset existing annotation in two scenarios:
                #  1. Previous annotation stopped (file no longer present)
                #  2. There is a new annotation (label has changed)
                if self.__lastAnnotationLabel != None and (
                    not userFileExists or self.__lastAnnotationLabel != data["annotation"]
                ):
                    self.__RMSMetrics["annotations"].labels(
                        marker=self.__lastAnnotationLabel,
                        jobid=results["SLURM_JOB_ID"],
                    ).set(0)
                    self.__lastAnnotationLabel = None

                if userFileExists:
                    self.__RMSMetrics["annotations"].labels(
                        marker=data["annotation"],
                        jobid=results["SLURM_JOB_ID"],
                    ).set(data["timestamp_secs"])
                    self.__lastAnnotationLabel = data["annotation"]

        # Case when no job detected
        else:
            self.__RMSMetrics["info"].labels(jobid="", user="", partition="", nodes="", batchflag="").set(1)

        return