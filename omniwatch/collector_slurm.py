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

"""SLURM data collector

Implements a prometheus info metric to track SLURM job-related info.  The
default resulting metric is named "slurmjob_info{}" and is always published.  An
optional "slurmjob_annotations{}" metric can be published to provide
user-provided annotation timestamps.
"""

import sys
import json
import logging
import os
import platform

from prometheus_client import Gauge, generate_latest, CollectorRegistry

import omniwatch.utils as utils
from omniwatch.collector_base import Collector

class SlurmJob(Collector):
    def __init__(self,userMode=False,annotations=False):
        logging.debug("Initializing SlurmJob data collector")
        self.__prefix = "slurmjob_"
        self.__userMode = userMode
        self.__annotationsEnabled = annotations
        self.__SLURMmetrics = {}
        self.__slurmJobInfo = []
        self.__lastAnnotationLabel = None

        # setup squeue binary path to query slurm to determine node ownership
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

        # cache current slurm job in user mode profiling - assumption is it doesn't change
        if self.__userMode is True:
            # read from file if available
            jobFile = "/tmp/omniwatch_slurm_job_assigned"
            if os.path.isfile(jobFile):
                with open(jobFile,'r') as f:
                    jobInfo = json.load(f)

                logging.info(jobInfo)
                self.__slurmJobInfo = []
                self.__slurmJobInfo.append(jobInfo["SLURM_JOB_ID"])
                self.__slurmJobInfo.append(jobInfo["SLURM_JOB_USER"])
                self.__slurmJobInfo.append(jobInfo["SLURM_JOB_PARTITION"])
                self.__slurmJobInfo.append(jobInfo["SLURM_JOB_NUM_NODES"])
                self.__slurmJobInfo.append(jobInfo["SLURM_JOB_BATCHMODE"])

                logging.info("--> usermode jobinfo (from file): %s" % self.__slurmJobInfo)

            else:
                # no job file data available: query slurm directly
                # note: a longer timeout is provided since we only query once and some systems have slow
                # slurm response times
                logging.info("User mode collector enabled for SLURM, querying job info once at startup...")

                data = self.querySlurmJob(timeout=15,exit_on_error=True)
                if data.stdout.strip():
                    self.__slurmJobInfo = data.stdout.strip().split(":")
                    logging.info("--> usermode jobinfo (from slurm query): %s" % self.__slurmJobInfo)
        else:
            logging.info("collector_slurm: not using usermode, will poll slurm periodicaly")

    def querySlurmJob(self,timeout=1,exit_on_error=False):
        data = utils.runShellCommand(self.__squeue_query,timeout=timeout,exit_on_error=exit_on_error)
        return(data)

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
        self.__SLURMmetrics["info"].clear()
        self.__SLURMmetrics["annotations"].clear()
        jobEnabled = False

        if self.__userMode is True:
            results = self.__slurmJobInfo
            jobEnabled = True
        else:
            data = self.querySlurmJob()
            # query output format:
            # JOBID,USER,PARTITION,NODES,CPUS
            if data.stdout.strip():
                results = data.stdout.strip().split(":")
                jobEnabled = True

        # Case when SLURM job is allocated
        if jobEnabled:
            self.__SLURMmetrics["info"].labels(
                jobid=results[0],
                user=results[1],
                partition=results[2],
                nodes=results[3],
                batchflag=results[4],
            ).set(1)

            # Check for user supplied annotations
            if self.__annotationsEnabled:
                userFile = "/tmp/omniwatch_%s_annotate.json" % results[1]

                userFileExists = os.path.isfile(userFile)
                if userFileExists:
                    with open(userFile, "r") as file:
                        data = json.load(file)

                # Reset existing annotation in two scenarios:
                #  1. Previous annotation stopped (file no longer present)
                #  2. There is a new annotation (label has changed)
                if self.__lastAnnotationLabel != None and (
                    not userFileExists
                    or self.__lastAnnotationLabel != data["annotation"]
                ):
                    self.__SLURMmetrics["annotations"].labels(
                        marker=self.__lastAnnotationLabel,
                        jobid=results[0],
                    ).set(0)
                    self.__lastAnnotationLabel = None

                if userFileExists:
                    self.__SLURMmetrics["annotations"].labels(
                        marker=data["annotation"],
                        jobid=results[0],
                    ).set(data["timestamp_secs"])
                    self.__lastAnnotationLabel = data["annotation"]

        # Case when no job detected
        else:
            self.__SLURMmetrics["info"].labels(
                jobid="", user="", partition="", nodes="", batchflag=""
            ).set(1)

        return