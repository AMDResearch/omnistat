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

from prometheus_client import Gauge

from omnistat.collector_base import Collector
from omnistat.job_metrics_collector import get_job_info


class RMSJobV2(Collector):
    def __init__(self):
        logging.debug("Initializing resource manager job data collector")
        self.__prefix = "rmsjob_"
        self.__RMSMetrics = {}
        self.__RunningJobs = {}
        self.__rmsJobInfo = []
        self.__lastAnnotationLabel = None
        self.c = 0

    def registerMetrics(self):
        """Register metrics of interest"""

        # alternate approach - define an info metric
        # (https://ypereirareis.github.io/blog/2020/02/21/how-to-join-prometheus-metrics-by-label-with-promql/)
        labels = ["jobid", "start_time", "end_time", "submit_time", "node", "card", "user", "account"]
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
                    self.__RMSMetrics["info"].remove(metric[0], metric[1], metric[2], metric[3], metric[4], metric[5], metric[6], metric[7])
                except:
                    pass

        return

    def collect_data_incremental(self):
        self.c += 1
        jobs = get_job_info()

        for job in jobs:
            jobid = job.get("job_id")
            start_time = job.get("start_time")
            end_time = job.get("end_time")
            submit_time = job.get("submit_time")
            gpus = job.get("GPUs")
            user = job.get("user_name")
            account = job.get("account")

            if not gpus:
                gpus = [""]
            for gpu in gpus:
                # add domain suffix
                node = gpu.split(":")[0] + ".amd.com"  # temp hack
                gpu = gpu.split(":")[-1]
                metric_tuple = (jobid, start_time, end_time, submit_time, node, gpu, user, account)
                self.__RunningJobs[metric_tuple] = self.c
                self.__RMSMetrics["info"].labels(
                    jobid=jobid,
                    start_time=start_time,
                    end_time=end_time,
                    submit_time=submit_time,
                    node=node,
                    card=gpu,
                    user=user,
                    account=account,
                ).set(1)

        return