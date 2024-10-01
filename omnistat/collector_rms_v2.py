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

import logging
import platform
import re
from prometheus_client import Gauge
from omnistat import utils
from omnistat.collector_base import Collector
import json


class RMSJobV2(Collector):
    def __init__(self):
        logging.debug("Initializing resource manager job data collector")
        self.__prefix = "rmsjob_"
        self.__RMSMetrics = {}
        self.__RunningJobs = {}
        self.__rmsJobInfo = []
        self.__lastAnnotationLabel = None
        self.c = 0

        # setup squeue binary path to query slurm to determine node ownership
        command = utils.resolvePath("squeue", "SLURM_PATH")
        # command-line flags for use with squeue to obtained desired metrics
        self.hostname = platform.node().split(".", 1)[0]
        flags = "-w " + self.hostname + " -h  --Format=JobID::,UserName::,Partition::,NumNodes::,BatchFlag"
        # cache query command with options
        self.__squeue_query = [command] + flags.split()
        # job step query command
        flags = "-s -w " + self.hostname + " -h --Format=StepID"
        self.__squeue_steps = [command] + flags.split()
        logging.debug("sqeueue_exec = %s" % self.__squeue_query)

    def registerMetrics(self):
        """Register metrics of interest"""

        # alternate approach - define an info metric
        # (https://ypereirareis.github.io/blog/2020/02/21/how-to-join-prometheus-metrics-by-label-with-promql/)
        labels = ["jobid", "user", "partition", "nodes", "batchflag", "jobstep", "type", "account", "card"]
        self.__RMSMetrics["info"] = Gauge(self.__prefix + "info", "RMS job details", labels)

        for metric in self.__RMSMetrics:
            logging.debug("--> Registered RMS metric = %s" % metric)

    def updateMetrics(self):

        self.collect_data_incremental()
        # Remove old labels for jobs not currently running
        for metric, counter in self.__RunningJobs.items():
            if counter < self.c:
                # catch edge case for multiple metrics with same name
                try:
                    self.__RMSMetrics["info"].remove(metric[0], metric[1], metric[2], metric[3], metric[4], metric[5], metric[6], metric[7], metric[8])
                except Exception as e:
                    logging.error(f"Failed to remove metric: {metric}\n"
                                  f"error: {e}\n"
                                  f"Running Jobs: {self.__RunningJobs}\n"
                                  f"Metrics: {self.__RMSMetrics}")
                    pass

        return

    def querySlurmJob(self, timeout=1, exit_on_error=False, mode="squeue"):
        """
        Query SLURM and return job info for local host.
        Supports two query modes: squeue call and read from file.

        Returns dictionary containing job id, user, partition, # of nodes, and batchmode flag
        """
        keys = [
            "RMS_JOB_ID",
            "RMS_JOB_USER",
            "RMS_JOB_PARTITION",
            "RMS_JOB_NUM_NODES",
            "RMS_JOB_BATCHMODE",
        ]
        results = []

        if mode == "squeue":
            squeue_data = utils.runShellCommand(self.__squeue_query, timeout=timeout, exit_on_error=exit_on_error)
            # squeue query output format: JOBID:USER:PARTITION:NUM_NODES:BATCHFLAG
            squeue_data_out = squeue_data.stdout.strip()
            if squeue_data_out:
                for job in squeue_data_out.splitlines():
                    data = job.strip().split(":")
                    r_job = dict(zip(keys, data))
                    r_job["RMS_TYPE"] = "slurm"

                    # require a 2nd query to ascertain job steps (otherwise, miss out on batchflag)
                    squeue_step_data = utils.runShellCommand(self.__squeue_steps, timeout=timeout, exit_on_error=exit_on_error)
                    r_job["RMS_STEP_ID"] = -1
                    if squeue_step_data.stdout.strip():
                        # If we are in an active job step, the STEPID will have an integer index appended, e.g.
                        # 57735.10
                        # 57735.interactive
                        stepField = (squeue_step_data.stdout.splitlines()[0]).strip()
                        jobstep = stepField.split(".")[1]
                        if jobstep.isdigit():
                            r_job["RMS_STEP_ID"] = jobstep
                    results.append(r_job)

        return results


    def get_job_info(self, job_id):

        def gpuinfo(nodelist, greslist, tres):
            gpu_list = [""]
            # Ensure the lengths of nodelist and greslist match
            if tres and len(greslist) != len(nodelist):
                logging.error(f"Length of nodelist and greslist do not match."
                              f"\ntres: {tres}\nnodelist: {nodelist}\ngreslist: {greslist}")
                return gpu_list

            # Find the index of the current node in the nodelist
            try:
                index = nodelist.index(self.hostname)
            except ValueError:
                logging.error(f"Node {self.hostname} not found in nodelist {nodelist}")
                return gpu_list

            # Extract GPU data for the current node
            gpu_data = greslist[index]
            gpu_list = expand_gpu(gpu_data)  # Expand the GPU data
            return gpu_list

        def expand_gpu(input_str):
            indexes = input_str.split("(IDX:")[-1].split(")")[0]
            if not indexes:
                return [""]
            temp = [(lambda sub: range(sub[0], sub[-1] + 1))(list(map(int, ele.split('-')))) for ele in
                    indexes.split(',')]
            res = [b for a in temp for b in a]
            return res

        def expand_number_range(input_str):
            if not isinstance(input_str, str):
                return [input_str]
            # Match the pattern with numbers and ranges inside square brackets
            match = re.search(r'(.+)\[(.+)\]', input_str)
            if match:
                prefix = match.group(1)
                ranges = match.group(2).split(',')
                expanded_list = []

                for item in ranges:
                    if '-' in item:
                        start, end = map(int, item.split('-'))
                        width = len(item.split('-')[0])  # Preserve leading zeros
                        expanded_list.extend([f"{prefix}{i:0{width}}" for i in range(start, end + 1)])
                    else:
                        expanded_list.append(f"{prefix}{item}")

                return expanded_list
            else:
                return [input_str]

        result = {}

        scontrol_data = utils.runShellCommand(['scontrol', 'show', 'job', job_id.strip(), '-d', '--json'],
                                              capture_output=True, text=True)
        if not scontrol_data.stdout.strip():
            logging.error(f"Failed to get job info for job: {job_id}, Error: {scontrol_data.stderr}")
            return {}
        job_data = json.loads(scontrol_data.stdout.strip())['jobs'][0]

        job_resources = job_data.get('job_resources', {})
        tres_string = job_data.get('tres_per_job', "")
        node_list = expand_number_range(job_resources.get('nodes', []))
        gres_list = job_data.get('gres_detail', [])
        gpus = gpuinfo(node_list, gres_list, tres_string)

        result["account"] = job_data.get('account', "")
        result["gpus"] = gpus

        return result

    def collect_data_incremental(self):
        self.c += 1
        jobs = self.querySlurmJob()

        keys = [
            "RMS_JOB_ID",
            "RMS_JOB_USER",
            "RMS_JOB_PARTITION",
            "RMS_JOB_NUM_NODES",
            "RMS_JOB_BATCHMODE",
            "RMS_STEP_ID",
            "RMS_TYPE"
        ]
        labels = ["jobid", "user", "partition", "nodes", "batchflag", "jobstep", "type", "account", "card"]
        for job in jobs:
            jobid = job.get("RMS_JOB_ID")
            user = job.get("RMS_JOB_USER")
            partition = job.get("RMS_JOB_PARTITION")
            num_nodes = job.get("RMS_JOB_NUM_NODES")
            batchmode = job.get("RMS_JOB_BATCHMODE")
            stepid = job.get("RMS_STEP_ID")
            jobtype = job.get("RMS_TYPE")
            try:
                results = self.get_job_info(jobid)
                account = results["account"]
                gpus = results["gpus"]
            except Exception as e:
                account = ""
                gpus = [""]
                logging.error(f"Failed to get job info for job: {jobid}\nError: {e}")

            if not gpus:
                gpus = [""]
            for gpu in gpus:
                metric_tuple = (jobid, user, partition, num_nodes, batchmode, stepid, jobtype, account, gpu)
                self.__RunningJobs[metric_tuple] = self.c
                self.__RMSMetrics["info"].labels(
                    jobid=jobid,
                    user=user,
                    partition=partition,
                    nodes=num_nodes,
                    batchflag=batchmode,
                    jobstep=stepid,
                    type=jobtype,
                    account=account,
                    card=gpu
                ).set(1)

        return
