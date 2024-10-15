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

import json
import logging
import os
import platform
import sys
import time
import zmq

from prometheus_client import Gauge

import omnistat.utils as utils
from omnistat.collector_base import Collector


class RMSJob(Collector):
    def __init__(self, annotations=False, annotationsPath="/tmp/omnistat_trace", jobDetection=None):
        logging.debug("Initializing resource manager job data collector")
        self.__prefix = "rmsjob_"
        self.__RMSMetrics = {}
        self.__rmsJobInfo = []
        self.__rmsJobMode = jobDetection["mode"]
        self.__rmsJobFile = jobDetection["file"]
        self.__rmsJobStepFile = jobDetection["stepfile"]

        self.__annotationsEnabled = annotations
        self.__annotationsJobID = None
        self.__spans = {}
        self.__context = None
        self.__socket = None

        # jobMode
        if self.__rmsJobMode == "file-based":
            logging.info(
                "collector_rms: reading job information from prolog/epilog derived file (%s)" % self.__rmsJobFile
            )
        elif self.__rmsJobMode == "squeue":
            logging.info("collector_rms: configured to poll slurm periodically with squeue")

            # setup squeue binary path to query slurm to determine node ownership
            command = utils.resolvePath("squeue", "SLURM_PATH")
            if command is None:
                logging.error("")
                logging.error("Please verify SLURM is installed and squeue binary is available")
                logging.error("")
                sys.exit(4)
            # command-line flags for use with squeue to obtained desired metrics
            hostname = platform.node().split(".", 1)[0]
            flags = "-w " + hostname + " -h  --Format=JobID::,UserName::,Partition::,NumNodes::,BatchFlag"
            # cache query command with options
            self.__squeue_query = [command] + flags.split()
            # job step query command
            flags = "-s -w " + hostname + " -h --Format=StepID"
            self.__squeue_steps = [command] + flags.split()
            logging.debug("sqeueue_exec = %s" % self.__squeue_query)
        else:
            logging.error("Unsupported slurm job data collection mode")

        if self.__annotationsEnabled:
            if os.path.exists(annotationsPath):
                os.remove(annotationsPath)
            self.__context = zmq.Context()
            self.__socket = self.__context.socket(zmq.PULL)
            self.__socket.bind(f"ipc://{annotationsPath}")

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
                    "RMS_JOB_ID",
                    "RMS_JOB_USER",
                    "RMS_JOB_PARTITION",
                    "RMS_JOB_NUM_NODES",
                    "RMS_JOB_BATCHMODE",
                ]
                results = dict(zip(keys, data))
                results["RMS_TYPE"] = "slurm"

                # require a 2nd query to ascertain job steps (otherwise, miss out on batchflag)
                data = utils.runShellCommand(self.__squeue_steps, timeout=timeout, exit_on_error=exit_on_error)
                results["RMS_STEP_ID"] = -1
                if data.stdout.strip():
                    # If we are in an active job step, the STEPID will have an integer index appended, e.g.
                    # 57735.10
                    # 57735.interactive
                    stepField = (data.stdout.splitlines()[0]).strip()
                    jobstep = stepField.split(".")[1]
                    if jobstep.isdigit():
                        results["RMS_STEP_ID"] = jobstep

        elif mode == "file-based":
            # preference is given to job step file if it exists
            if os.path.isfile(self.__rmsJobStepFile):
                with open(self.__rmsJobStepFile, "r") as file:
                    results = json.load(file)
            elif os.path.isfile(self.__rmsJobFile):
                with open(self.__rmsJobFile, "r") as file:
                    results = json.load(file)

        return results

    def registerMetrics(self):
        """Register metrics of interest"""

        # alternate approach - define an info metric
        # (https://ypereirareis.github.io/blog/2020/02/21/how-to-join-prometheus-metrics-by-label-with-promql/)
        labels = ["jobid", "user", "partition", "nodes", "batchflag", "jobstep", "type"]
        self.__RMSMetrics["info"] = Gauge(self.__prefix + "info", "RMS job details", labels)

        # metric to support user annotations
        self.__RMSMetrics["annotations"] = Gauge(
            self.__prefix + "annotations", "User job annotations", ["marker", "jobid", "traceid"]
        )

        for metric in self.__RMSMetrics:
            logging.debug("--> Registered RMS metric = %s" % metric)

    def updateMetrics(self):
        self.__RMSMetrics["info"].clear()
        self.__RMSMetrics["annotations"].clear()
        jobEnabled = False

        results = None

        results = self.querySlurmJob(mode=self.__rmsJobMode)
        if results:
            jobEnabled = True

        # Case when SLURM job is allocated
        if jobEnabled:
            self.__RMSMetrics["info"].labels(
                jobid=results["RMS_JOB_ID"],
                user=results["RMS_JOB_USER"],
                partition=results["RMS_JOB_PARTITION"],
                nodes=results["RMS_JOB_NUM_NODES"],
                batchflag=results["RMS_JOB_BATCHMODE"],
                jobstep=results["RMS_STEP_ID"],
                type=results["RMS_TYPE"],
            ).set(1)

            # Check for user supplied annotations
            if self.__annotationsEnabled:
                self.updateAnnotations(results["RMS_JOB_ID"])

        # Case when no job detected
        else:
            self.__RMSMetrics["info"].labels(
                jobid="", user="", partition="", nodes="", batchflag="", jobstep="", type=""
            ).set(1)

        return

    def updateAnnotations(self, jobid):
        # Reset annotations when a new job is running
        if jobid != self.__annotationsJobID:
            self.__spans = {}
            self.__annotationsJobID = jobid

        # Read all annotation messages until work queue is empty
        messages = []
        while True:
            try:
                msg = self.__socket.recv_json(flags=zmq.NOBLOCK)
                messages.append(msg)
            except zmq.ZMQError as e:
                break

        # Process start/end messages
        for kind, time_ms, trace_id, label in messages:
            if trace_id not in self.__spans:
                self.__spans[trace_id] = {"started": {}, "ended": {}}

            if kind == "start":
                if label in self.__spans[trace_id]["ended"]:
                    self.__spans[trace_id]["ended"].pop(label)
                self.__spans[trace_id]["started"][label] = time_ms
            elif kind == "end":
                if label in self.__spans[trace_id]["started"]:
                    self.__spans[trace_id]["started"].pop(label)
                self.__spans[trace_id]["ended"][label] = time_ms

        # Completed spans need to remain visible for a while to make
        # sure Prometheus can identify the completion
        time_ms = time.time_ns() // 1_000_000
        cutoff_ms = 15_000

        # Remove old spans that are no longer needed
        for trace_id, spans in self.__spans.items():
            remove = []
            for label, end_ms in spans["ended"].items():
                if end_ms < time_ms - cutoff_ms:
                    remove.append(label)
            for label in remove:
                self.__spans[trace_id]["ended"].pop(label)

        # Set annotation metrics in Prometheus
        for trace_id, spans in self.__spans.items():
            for label in spans["started"].keys():
                self.__RMSMetrics["annotations"].labels(
                    marker=label,
                    jobid=jobid,
                    traceid=trace_id,
                ).set(1)

            for label in spans["ended"].keys():
                self.__RMSMetrics["annotations"].labels(
                    marker=label,
                    jobid=str(jobid),
                    traceid=str(trace_id),
                ).set(0)
