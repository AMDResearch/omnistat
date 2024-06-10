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
import utils
import json
import logging
import os
import platform
from collector_base import Collector
from prometheus_client import Gauge, generate_latest, CollectorRegistry


class SlurmJob(Collector):
    def __init__(self,userMode=False,annotations=False,jobDetection=None):
        logging.debug("Initializing SlurmJob data collector")
        self.__prefix = "slurmjob_"
        self.__userMode = userMode
        self.__annotationsEnabled = annotations
        self.__SLURMmetrics = {}
        self.__slurmJobInfo = []
        self.__lastAnnotationLabel = None
        self.__slurmJobMode = jobDetection['mode']
        self.__slurmJobFile = jobDetection['file']

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

        # cache current slurm job in user mode profiling - assumption is that it does not change
        if self.__userMode is True:
            # read from file if available
            jobFile = self.__slurmJobFile
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
            if self.__slurmJobMode == 'file-based':
                logging.info("collector_slurm: reading job information from prolog/epilog derived file (%s)" % self.__slurmJobFile)
            elif self.__slurmJobMode == 'squeue':
                logging.info("collector_slurm: will poll slurm periodicaly with squeue")
            else:
                logging.error("Unsupported slurm job data collection mode")

    def querySlurmJob(self,timeout=1,exit_on_error=False):
        """
        Query SLURM and return job info for local host.

        Return dictionary containing job id, user, partition, # of nodes, and batchmode flag
        """

        results = {}
        if self.__slurmJobMode == 'squeue':
            data = utils.runShellCommand(self.__squeue_query,timeout=timeout,exit_on_error=exit_on_error)
            # squeue query output format: JOBID:USER:PARTITION:NUM_NODES:BATCHFLAG
            if data.stdout.strip():
                data = data.stdout.strip().split(":")
                keys = ["SLURM_JOB_ID","SLURM_JOB_USER","SLURM_JOB_PARTITION","SLURM_JOB_NUM_NODES","SLURM_JOB_BATCHMODE"]
                results = dict(zip(keys,data))
        elif self.__slurmJobMode == 'file-based':
            jobFileExists = os.path.isfile(self.__slurmJobFile)
            if jobFileExists:
                with open(self.__slurmJobFile, "r") as file:
                    results = json.load(file)
        return(results)

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

        results = None

        if self.__userMode is True:
            results = self.__slurmJobInfo
            jobEnabled = True
        else:
            results = self.querySlurmJob()
            if results:
                jobEnabled = True

        # Case when SLURM job is allocated
        if jobEnabled:
            self.__SLURMmetrics["info"].labels(
                jobid=results["SLURM_JOB_ID"],
                user=results["SLURM_JOB_USER"],
                partition=results["SLURM_JOB_PARTITION"],
                nodes=results["SLURM_JOB_NUM_NODES"],
                batchflag=results["SLURM_JOB_BATCHMODE"],
            ).set(1)

            # Check for user supplied annotations
            if self.__annotationsEnabled:
                userFile = "/tmp/omniwatch_%s_annotate.json" % results["SLURM_JOB_USER"]

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
                        jobid=results["SLURM_JOB_ID"],
                    ).set(0)
                    self.__lastAnnotationLabel = None

                if userFileExists:
                    self.__SLURMmetrics["annotations"].labels(
                        marker=data["annotation"],
                        jobid=results["SLURM_JOB_ID"],
                    ).set(data["timestamp_secs"])
                    self.__lastAnnotationLabel = data["annotation"]

        # Case when no job detected
        else:
            self.__SLURMmetrics["info"].labels(
                jobid="", user="", partition="", nodes="", batchflag=""
            ).set(1)

        return
