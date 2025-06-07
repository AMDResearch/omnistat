#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2023 - 2025 Advanced Micro Devices, Inc. All Rights Reserved.
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

import argparse
import logging
import os
import shutil
import subprocess
import sys
import timeit
from datetime import datetime, timedelta
from pathlib import Path
from string import Template

import matplotlib.dates as mdates
import matplotlib.pylab as plt
import numpy as np
import pandas
from prometheus_api_client import MetricRangeDataFrame, PrometheusConnect
from prometheus_api_client.utils import parse_datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from omnistat import utils


class queryMetrics:

    def __init__(self, versionData):
        self.timer_start = timeit.default_timer()

        self.config = {}
        self.enable_redirect = False
        self.output_file = None
        self.pdf = None

        self.jobinfo = None
        self.jobID = None
        self.jobStep = None
        self.numGPUs = None

        self.start_time = None
        self.end_time = None
        self.interval = None

        self.prometheus = None

        # Define metrics to report on (set 'title_short' to indicate inclusion in statistics summary)
        self.metrics = [
            {
                "metric": "rocm_utilization_percentage",
                "title": "GPU Core Utilization",
                "title_short": "Utilization (%)",
            },
            {"metric": "rocm_vram_used_percentage", "title": "GPU Memory Used (%)", "title_short": "Memory Use (%)"},
            {
                "metric": "rocm_temperature_celsius",
                "title": "GPU Temperature (C)",
                "title_short": "Temperature (C)",
            },
            {"metric": "rocm_sclk_clock_mhz", "title": "GPU Clock Frequency (MHz)"},
            {"metric": "rocm_average_socket_power_watts", "title": "GPU Average Power (W)", "title_short": "Power (W)"},
        ]

        # self.sha = versionData["sha"]
        # self.version = versionData["version"]
        self.version = versionData

    def __del__(self):
        if hasattr(self, "enable_redirect"):
            if self.enable_redirect:
                self.output.close()

    def read_config(self, configFileArgument):
        runtimeConfig = utils.readConfig(utils.findConfigFile(configFileArgument))
        section = "omnistat.query"
        self.config["system_name"] = runtimeConfig[section].get("system_name", "My Snazzy Cluster")
        self.config["prometheus_url"] = runtimeConfig[section].get("prometheus_url", "unknown")

    def __del__(self):
        if self.enable_redirect:
            self.output.close()

    def set_options(self, jobID=None, output_file=None, pdf=None, interval=None, step=None):
        if jobID:
            self.jobID = jobID
        if output_file:
            self.output_file = output_file
        if pdf:
            self.pdf = pdf

        # define jobstep label query (either given by user or matches all job steps)
        if step:
            self.jobStep = step
            self.jobstepQuery = f'jobstep="{step}"'
        else:
            self.jobstepQuery = 'jobstep=~".*"'
        logging.debug("Job step query set to -> %s" % self.jobstepQuery)

        self.interval = interval
        return

    def setup(self):

        # (optionally) redirect stdout
        if self.output_file:
            if not os.path.isfile(self.output_file):
                sys.exit()
            else:
                self.output = open(self.output_file, "a")
                sys.stdout = self.output
                self.enable_redirect = True

        self.prometheus = PrometheusConnect(url=self.config["prometheus_url"])

        # The scan step is used in the initial queries to find the start and
        # end time of the job, as well as other details in the info metric. It
        # can't be too low because queries have a maximum number of points per
        # request (the default in Victoria Metrics is 30,000), and we need to
        # potentially generate up to 365 queries to find a job in the last
        # year (1 query/day).
        #
        # To remain within the maximum number of points per request, we select
        # a scan step between 5s (17,280 points/day) and 60s (1,440
        # points/day) depending on the interval. While it's technically
        # possible to always use the smallest scan step, we gradually increase
        # the step based on interval to make these queries more efficient.
        # Our assumption is jobs with longer intervals are generally longer.
        #
        # Jobs with intervals under 30s require a minimum execution time to
        # guarantee they can be located in the database:
        #  -  5s of execution for intervals under 1s
        #  - 15s of execution for intervals between 1s and 30s
        #
        # For jobs with intervals over 30s, the scan step is equal or lower
        # than the interval, and so no minimum execution time is required.
        if self.interval < 1:
            self.scan_step = 5
        elif self.interval >= 1 and self.interval < 30:
            self.scan_step = 15
        elif self.interval >= 30 and self.interval < 60:
            self.scan_step = 30
        else:
            self.scan_step = 60

        # query jobinfo
        self.jobinfo = self.query_slurm_job_internal()
        if self.jobinfo["begin_date"] == "Unknown":
            print("Job %s has not run yet." % self.jobID)
            sys.exit(0)

        self.start_time = datetime.strptime(self.jobinfo["begin_date"], "%Y-%m-%dT%H:%M:%S")
        if self.jobinfo["end_date"] == "Unknown":
            self.end_time = datetime.now()
        else:
            self.end_time = datetime.strptime(self.jobinfo["end_date"], "%Y-%m-%dT%H:%M:%S")

        # NOOP if job is very short running
        runtime = (self.end_time - self.start_time).total_seconds()
        if runtime < 61:
            logging.info("--> Short duration job detected...(%.1f secs) - unsupported query." % runtime)
            sys.exit()

        # cache hosts assigned to job
        self.get_hosts()


    def query_jobinfo(self, start, end):
        """
        Query job data info given start/stop time window.

        Args:
            start (datetime): Approximate start time of the job.
            end (datetime): Approximate end time of the job.

        Returns:
            dict: Job info data.
        """

        # To provide more accurate timing, generate two queries with small
        # ranges: one around the start time and the other one around the end
        # time. The original start/end times based on the initial scan are as
        # accurate as the scan step; the start/end times as updated here are
        # as accurate as the interval.
        delta = timedelta(seconds=self.scan_step * 2)
        start_range = (start, start - delta)
        end_range = (end - delta, end)

        start_results = self.query_range("rmsjob_info{$job,$step}", start_range[0], start_range[1], self.interval)
        if len(start_results) > 0:
            start = datetime.fromtimestamp(start_results[0]["values"][0][0])

        end_results = self.query_range("rmsjob_info{$job,$step}", end_range[0], end_range[1], self.interval)
        if len(end_results) > 0:
            end = datetime.fromtimestamp(end_results[0]["values"][-1][0])

        duration_mins = (end - start).total_seconds() / 60
        assert duration_mins > 0

        # assemble coarsened query step based on job duration
        if duration_mins > 60:
            coarse_step = "1h"
        elif duration_mins > 15:
            coarse_step = "15m"
        elif duration_mins > 5:
            coarse_step = "5m"
        else:
            # For short jobs, use the same step as the scan step (between 5
            # and 60 seconds depending on interval).
            coarse_step = self.scan_step

        # Cull job info with coarse resolution
        results = self.query_range("rmsjob_info{$job,$step}", start, end, coarse_step)
        assert len(results) > 0

        num_nodes = int(results[0]["metric"]["nodes"])
        partition = results[0]["metric"]["partition"]

        # Cull number of gpus with coarse resolution
        results = self.query_range("rocm_num_gpus * on (instance) rmsjob_info{$job,$step}", start, end, coarse_step)
        assert len(results) > 0

        num_gpus = int(results[0]["values"][0][1])
        assert num_gpus > 0

        # warn if nodes do not have same gpu counts
        for node in range(len(results)):
            value = int(results[node]["values"][0][1])
            if value != num_gpus:
                print("[WARNING]: compute nodes detected with differing number of GPUs (%i,%i) " % (num_gpus, value))
                break

        self.numGPUs = num_gpus

        jobdata = {}
        jobdata["begin_date"] = start.strftime("%Y-%m-%dT%H:%M:%S")
        jobdata["end_date"] = end.strftime("%Y-%m-%dT%H:%M:%S")
        jobdata["num_nodes"] = num_nodes
        jobdata["partition"] = partition
        return jobdata

    # gather relevant job data from info metric
    def query_slurm_job_internal(self):

        firstTimestamp = None
        lastTimestamp = None

        now = datetime.now()

        # loop over days starting from now to find time window covering desired job
        for day in range(365):
            aend = now - timedelta(days=day)
            astart = aend - timedelta(days=1)

            results = self.query_range("max(rmsjob_info{$job,$step})", astart, aend, self.scan_step)
            if not lastTimestamp and len(results) > 0:
                lastTimestamp = datetime.fromtimestamp(results[0]["values"][-1][0])
                endWindow = aend
                firstTimestamp = datetime.fromtimestamp(results[0]["values"][0][0])
                continue
            elif lastTimestamp and len(results) > 0:
                firstTimestamp = datetime.fromtimestamp(results[0]["values"][0][0])
                continue
            elif lastTimestamp and len(results) == 0:
                break

        if not firstTimestamp:
            print("[ERROR]: no monitoring data found for job=%s" % self.jobID)
            sys.exit(1)

        # expand job window to nearest scan step
        firstTimestamp -= timedelta(seconds=self.scan_step)
        lastTimestamp += timedelta(seconds=self.scan_step)

        jobdata = self.query_jobinfo(firstTimestamp, lastTimestamp)
        return jobdata

    # gather relevant job data from resource manager directly
    def query_slurm_job(self):
        id = self.jobID
        cmd = [
            "sacct",
            "-n",
            "-P",
            "-X",
            "-j",
            str(id),
            "--format",
            "Start,End,NNodes,Partition",
        ]
        path = shutil.which("sacct")
        if path is None:
            print("[ERROR]: unable to resolve 'sacct' binary")
            sys.exit(1)

        try:
            results = subprocess.check_output(cmd, universal_newlines=True).strip()
        except subprocess.CalledProcessError as e:
            print("[ERROR]: unable to query resource manager for job %i" % id)
            sys.exit(1)

        results = results.split("\n")

        # exit if no jobs found
        if not results[0]:
            print("No job found for id=%i" % id)
            sys.exit(0)

        jobdata = {}
        data = results[0].split("|")
        jobdata["begin_date"] = data[0]
        jobdata["end_date"] = data[1]
        jobdata["num_nodes"] = data[2]
        jobdata["partition"] = data[3]

        return jobdata

    # Detect hosts associated with this job
    def get_hosts(self):
        self.hosts = []
        results = self.query_range(
            'rocm_utilization_percentage{card="0"} * on (instance) rmsjob_info{$job}',
            self.start_time,
            self.end_time,
            self.scan_step,
        )
        self.totalNodes = len(results)

        if self.jobStep:
            results = self.query_range(
                'rocm_utilization_percentage{card="0"} * on (instance) rmsjob_info{$job,$step}',
                self.start_time,
                self.end_time,
                self.scan_step,
            )
            for result in results:
                self.hosts.append(result["metric"]["instance"])
            self.stepNodes = len(self.hosts)
        else:
            for result in results:
                self.hosts.append(result["metric"]["instance"])
            self.stepNodes = self.totalNodes

        assert self.stepNodes > 0
        assert self.totalNodes > 0
        if self.totalNodes != self.jobinfo["num_nodes"]:
            logging.warning("")
            logging.warning("[WARNING]: telemetry data not collected for all nodes assigned to this job")
            logging.warning("--> # assigned hosts     = %i" % self.jobinfo["num_nodes"])
            logging.warning("--> # of hosts with data = %i" % self.totalNodes)

    def metric_host_max_sum(self, values):
        """Determine host with <maximum> sum of all provided samples"""
        maxvalue = 0.0
        for i in range(len(values)):
            sum = values[i].sum()
            if sum > maxvalue:
                maxvalue = sum
                maxindex = i
        return maxindex, sum

    def metric_host_min_sum(self, values):
        """Determine host with <minimum> sum of all provided samples"""
        minvalue = sys.float_info.max
        for i in range(len(values)):
            sum = values[i].sum()
            if sum < minvalue:
                minvalue = sum
                minindex = i
        return minindex, sum

    def gather_data(self, saveTimeSeries=False):
        self.stats = {}
        self.time_series = {}
        self.max_GPU_memory_avail = []
        self.gpu_energy_total_kwh = 0
        self.energyStats_kwh = [None] * self.numGPUs
        self.mean_util_per_gpu = [None] * self.numGPUs

        for entry in self.metrics:
            metric = entry["metric"]

            self.stats[metric + "_min"] = []
            self.stats[metric + "_max"] = []
            self.stats[metric + "_mean"] = []

            if saveTimeSeries:
                self.time_series[metric] = []
                self.time_series[metric + "_hostmax_raw"] = []
                self.time_series[metric + "_hostmin_raw"] = []

            # # init tracking of min/max
            # minValue =  sys.float_info.max
            # maxValue = -sys.float_info.max

            for gpu in range(self.numGPUs):

                query_metric = f'{metric}{{card="{gpu}"}}'
                try:
                    # (1) capture time series that assembles [mean] value at each timestamp across all assigned nodes
                    times, values_mean = self.query_time_series_data(query_metric, "avg")

                    # (2) capture time series that assembles [max] value at each timestamp across all assigned nodes
                    times, values_max = self.query_time_series_data(query_metric, "max")

                    # (3) capture raw time series
                    times_raw, values_raw, hosts = self.query_time_series_data(query_metric)
                except:
                    utils.error("Unable to query prometheus data for metric -> %s" % query_metric)

                # Sum total energy across all hosts and gpus
                if metric == "rocm_average_socket_power_watts":
                    energy_per_host = []

                    energyTotal = 0.0
                    for i in range(len(times_raw)):
                        startDate = times_raw[i][0]
                        x = (times_raw[i] - startDate).astype("timedelta64[s]").astype(float)
                        # Integrate time series to get energy used on this host/gpu index
                        # Units: W x [sec] = Joules -> Convert to kWH
                        energy = np.trapezoid(values_raw[i], x=x) / (1000 * 3600)
                        # accumulate to get total energy used by all hosts with this gpu index
                        energyTotal += energy
                        energy_per_host.append(energy)

                    # total energy used by this gpu index across all hosts
                    self.gpu_energy_total_kwh += energyTotal
                    self.energyStats_kwh[gpu] = energy_per_host

                # # Track hosts with min/max area under the curve (across all GPUs)
                # if len(self.hosts) > 1:
                #     minId, sum_min = self.metric_host_min_sum(values_raw)
                #     maxId, sum_max = self.metric_host_max_sum(values_raw)

                # if gpu == 0:
                #     for i in range(len(times)):
                #         print("%s %s %s" % (times[i],values_mean[i], values_max[i]))
                # sys.exit(1)

                self.stats[metric + "_max"].append(np.max(values_max))
                self.stats[metric + "_mean"].append(np.mean(values_mean))

                if metric == "rocm_vram_used":
                    # compute % memory used
                    times2, values2_min = self.query_time_series_data("card" + str(gpu) + "_rocm_vram_total", "min")
                    times2, values2_max = self.query_time_series_data("card" + str(gpu) + "_rocm_vram_total", "max")

                    memoryMin = np.min(values2_min)
                    memoryMax = np.max(values2_max)
                    if memoryMin != memoryMax:
                        print("[ERROR]: non-homogeneous memory sizes detected on assigned compute nodes")
                        sys.exit(1)

                    memoryAvail = memoryMax
                    self.stats[metric + "_max"][-1] = 100.0 * self.stats[metric + "_max"][-1] / memoryAvail
                    self.stats[metric + "_mean"][-1] = 100.0 * self.stats[metric + "_mean"][-1] / memoryAvail
                    self.max_GPU_memory_avail.append(memoryAvail)
                    values_mean = 100.0 * values_mean / memoryAvail
                    values_max = 100.0 * values_max / memoryAvail

                # save mean utilization per individual gpu
                values = []
                if metric == "rocm_utilization":
                    for i in range(len(times_raw)):
                        mean = np.mean(values_raw[i])
                        values.append(mean)
                    self.mean_util_per_gpu[gpu] = values

                if saveTimeSeries:
                    self.time_series[metric].append({"time": times, "values": values_mean})
                    # self.time_series[metric + '_hostmax_raw'].append({'time':times_raw[maxId],'values':values_raw[maxId],'host':hosts[maxId]})
                    # self.time_series[metric + '_hostmin_raw'].append({'time':times_raw[minId],'values':values_raw[minId],'host':hosts[minId]})
        return

    def generate_report_card(self):
        system = self.config["system_name"]

        print("")
        print("-" * 70)
        print("Omnistat Report Card for Job Id: %s" % self.jobID)
        if self.jobStep:
            print(
                "** Report confined to job step=%s (%i of %i nodes used)"
                % (self.jobStep, self.stepNodes, self.totalNodes)
            )
        print("-" * 70)
        print("")
        print("Job Overview (Num Nodes = %i, Machine = %s)" % (len(self.hosts), system))
        print(" --> Start time = %s" % self.start_time)
        print(" --> End   time = %s" % self.end_time.strftime("%Y-%m-%d %H:%M:%S"))
        print("")
        print("GPU Statistics:")
        print("")
        print("    %6s |" % "", end="")
        for entry in self.metrics:
            if "title_short" in entry:
                # print("%16s |" % entry['title_short'],end='')
                print(" %s |" % entry["title_short"].center(16), end="")
        print("")
        print("    %6s |" % "GPU #", end="")
        for entry in self.metrics:
            if "title_short" in entry:
                print(" %8s%8s |" % ("Max".center(6), "Mean".center(6)), end="")
        print("")
        print("    " + "-" * 84)

        for card in range(self.numGPUs):
            print("    %6s |" % card, end="")
            for entry in self.metrics:
                if "title_short" not in entry:
                    continue
                metric = entry["metric"]
                print(
                    "  %6.2f  %6.2f  |" % (self.stats[metric + "_max"][card], self.stats[metric + "_mean"][card]),
                    end="",
                )
            print("")

        print("")
        print("Approximate Total GPU Energy Consumed = %.2f kWh" % self.gpu_energy_total_kwh)
        print("")

        print("--")
        print("Query interval = %.3f secs" % self.interval)
        print("Query execution time = %.1f secs" % (timeit.default_timer() - self.timer_start))
        version = self.version
        # if self.sha != "Unknown":
        #     version += " (%s)" % self.sha
        print("Version = %s" % version)
        return

    def query_range(self, query_template, start, end, step):
        """
        Request a given query in the provided range. The query may optionally
        include variables to select job ID ($job) and step ID ($step) labels,
        and which are automatically substituted for the appropriate value.

        Args:
            query_template (str): PromQL query with substitutions.
            start (datetime): Query start time.
            end (datetime): Query end time.
            step (str|float): Query resolution string with unit, or float in seconds.

        Result:
            dict: Metric data in response of the submitted query.
        """
        template = Template(query_template)
        query = template.substitute(job=f'jobid="{self.jobID}"', step=self.jobstepQuery)
        results = self.prometheus.custom_query_range(query, start, end, step=step)
        return results

    def query_job_range(self, query_template):
        """
        Request a given query in the job's range. The query may optionally
        include variables to select job ID ($job) and step ID ($step) labels,
        and which are automatically substituted for the appropriate value.

        Args:
            query_template (str): PromQL query with substitutions.

        Result:
            dict: Metric data in response of the submitted query.
        """
        results = self.query_range(query_template, self.start_time, self.end_time, self.interval)
        return results

    def query_time_series_data(self, metric_name, reducer=None, dataType=float):

        if reducer is None:
            query = "%s * on (instance) rmsjob_info{$job,$step}" % (metric_name)
            results = self.query_job_range(query)
        else:
            query = "%s(%s * on (instance) rmsjob_info{$job,$step})" % (reducer, metric_name)
            results = self.query_job_range(query)

        if reducer is None:
            # return lists with raw time series data from all hosts for given metric
            times = []
            values = []
            hosts = []

            for i in range(len(results)):
                tmpresult = np.asarray(results[i]["values"])
                # convert to time format
                tmptime = tmpresult[:, 0].astype(float).astype("datetime64[s]")
                if dataType == int:
                    tmpvalues = tmpresult[:, 1].astype(int)
                elif dataType == float:
                    tmpvalues = tmpresult[:, 1].astype(float)
                times.append(tmptime)
                values.append(tmpvalues)
                hosts.append(results[i]["metric"]["instance"])
            return times, values, hosts
        else:
            # only have a single time series when reduction operator applied
            results = np.asarray(results[0]["values"])

            # convert to time format
            time = results[:, 0].astype(float).astype("datetime64[s]")
            # let user decide on conversion type for gauge metric
            if dataType == int:
                values = results[:, 1].astype(int)
            elif dataType == float:
                values = results[:, 1].astype(float)
            return time, values

    # def query_gpu_metric(self, metricName):
    #     stats = {}
    #     stats["mean"] = []
    #     stats["max"] = []

    #     for gpu in range(self.numGPUs):
    #         metric = "card" + str(gpu) + "_" + metricName

    #         # --
    #         # Mean results
    #         results = self.prometheus.custom_query_range(
    #             'avg(%s * on (instance) rmsjob_info{jobid="%s"})' % (metric, self.jobID),
    #             self.start_time,
    #             self.end_time,
    #             step=60,
    #         )

    #         assert len(results) == 1
    #         data = results[0]["values"]
    #         data2 = np.asarray(data, dtype=float)
    #         stats["mean"].append(np.mean(data2[:, 1]))

    #         # --
    #         # Max results
    #         results = self.prometheus.custom_query_range(
    #             'max(%s * on (instance) rmsjob_info{jobid="%s"})' % (metric, self.jobID),
    #             self.start_time,
    #             self.end_time,
    #             step=60,
    #         )

    #         assert len(results) == 1
    #         data = results[0]["values"]
    #         data2 = np.asarray(data, dtype=float)
    #         stats["max"].append(np.max(data2[:, 1]))

    #     return stats

    def dumpFile(self, outputFile):
        doc = SimpleDocTemplate(
            outputFile,
            pagesize=letter,
            rightMargin=1 * inch,
            leftMargin=1 * inch,
            topMargin=62,
            bottomMargin=18,
            showBoundary=0,
        )

        styles = getSampleStyleSheet()
        normal = ParagraphStyle("normal")
        Story = []
        Story.append(Spacer(1, 0.1 * inch))
        Story.append(HRFlowable(width="100%", thickness=2))
        ptext = """
        <strong>Omnistat Report Card</strong>: JobID = %s<br/>
        <strong>Start Time</strong>: %s<br/>
        <strong>End Time</strong>: %s<br/>
        """ % (
            self.jobID,
            self.start_time,
            self.end_time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        Story.append(Paragraph(ptext, styles["Bullet"]))
        Story.append(HRFlowable(width="100%", thickness=2))
        if self.jobStep:
            ptext = """<strong>Job Step Mode</strong>: Report confined to job step = %s""" % (self.jobStep)
            Story.append(Paragraph(ptext))
            Story.append(HRFlowable(width="100%", thickness=2))

        # generate Utilization Table
        Story.append(Spacer(1, 0.2 * inch))
        ptext = """<strong>GPU Statistics</strong>"""
        Story.append(Paragraph(ptext, normal))
        Story.append(Spacer(1, 0.2 * inch))
        # Story.append(HRFlowable(width="100%",thickness=1))

        # --
        # Display general GPU Statistics
        # --

        data = []
        data.append(
            ["", "Utilization (%)", "", "Memory Use (%)", "", "Temperature (C)", "", "Power (W)", "", "Energy (kWh)"]
        )
        data.append(["GPU", "Max", "Mean", "Max", "Mean", "Max", "Mean", "Max", "Mean", "Total"])

        for gpu in range(self.numGPUs):
            data.append(
                [
                    gpu,
                    "%.2f" % self.stats["rocm_utilization_percentage_max"][gpu],
                    "%.2f" % self.stats["rocm_utilization_percentage_mean"][gpu],
                    "%.2f" % self.stats["rocm_vram_used_percentage_max"][gpu],
                    "%.2f" % self.stats["rocm_vram_used_percentage_mean"][gpu],
                    "%.2f" % self.stats["rocm_temperature_celsius_max"][gpu],
                    "%.2f" % self.stats["rocm_temperature_celsius_mean"][gpu],
                    "%.2f" % self.stats["rocm_average_socket_power_watts_max"][gpu],
                    "%.2f" % self.stats["rocm_average_socket_power_watts_mean"][gpu],
                    "%.2f" % np.sum(self.energyStats_kwh[gpu]),
                ]
            )

        t = Table(data, rowHeights=[0.21 * inch] * len(data), colWidths=[0.4 * inch] + [0.62 * inch] * 8 + [1 * inch])
        t.hAlign = "LEFT"
        t.setStyle(
            TableStyle([("LINEBELOW", (0, 1), (-1, 1), 1.5, colors.black), ("ALIGN", (0, 0), (-1, -1), "CENTER")])
        )
        t.setStyle(
            TableStyle(
                [
                    ("LINEBEFORE", (1, 0), (1, -1), 1.25, colors.darkgrey),
                    ("LINEAFTER", (2, 0), (2, -1), 1.25, colors.darkgrey),
                    ("LINEAFTER", (4, 0), (4, -1), 1.25, colors.darkgrey),
                    ("LINEAFTER", (6, 0), (6, -1), 1.25, colors.darkgrey),
                    ("LINEAFTER", (8, 0), (8, -1), 1.25, colors.darkgrey),
                ]
            )
        )
        t.setStyle(
            TableStyle(
                [("SPAN", (1, 0), (2, 0)), ("SPAN", (3, 0), (4, 0)), ("SPAN", (5, 0), (6, 0)), ("SPAN", (7, 0), (8, 0))]
            )
        )
        t.setStyle(TableStyle([("FONTSIZE", (1, 0), (-1, -1), 10)]))

        for each in range(2, len(data)):
            if each % 2 == 0:
                bg_color = colors.lightgrey
            else:
                bg_color = colors.whitesmoke

            t.setStyle(TableStyle([("BACKGROUND", (0, each), (-1, each), bg_color)]))
        Story.append(t)

        Story.append(Spacer(1, 0.2 * inch))

        ptext = """Approximate Total GPU Energy Consumed = %.2f kWh""" % (self.gpu_energy_total_kwh)
        Story.append(Paragraph(ptext, normal))

        # --
        # Display time-series plots
        # --

        Story.append(Spacer(1, 0.2 * inch))
        Story.append(HRFlowable(width="100%", thickness=1))
        Story.append(Spacer(1, 0.2 * inch))
        ptext = """<strong>Time Series</strong>"""
        Story.append(Paragraph(ptext, normal))
        Story.append(Spacer(1, 0.2 * inch))

        for entry in self.metrics:
            metric = entry["metric"]
            plt.figure(figsize=(9, 2.5))

            for gpu in range(self.numGPUs):
                plt.plot(
                    self.time_series[metric][gpu]["time"],
                    self.time_series[metric][gpu]["values"],
                    linewidth=0.4,
                    label="Card %i" % gpu,
                )
            #                         self.time_series[metric][gpu]['values'],marker='o',markersize=1,linewidth=0.4,label='Card %i' % gpu)
            # plt.plot(self.time_series[metric+'_hostmax_raw'][gpu]['time'],
            #          self.time_series[metric+'_hostmax_raw'][gpu]['values'],'--',linewidth=0.4,label=None)
            # wip - show high/low usage
            # plt.plot(self.time_series[metric+'_hostmin_raw'][gpu]['time'],
            #          self.time_series[metric+'_hostmin_raw'][gpu]['values'],'--',linewidth=0.4,label=None)

            plt.title(entry["title"])
            plt.legend(bbox_to_anchor=(1.0, 0.5), loc="center left", ncol=1, frameon=True)
            plt.grid()
            ax = plt.gca()

            locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
            formatter = mdates.ConciseDateFormatter(locator)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            plt.savefig(".utilization.png", dpi=150, bbox_inches="tight")
            plt.close()
            aplot = Image(".utilization.png")
            aplot.hAlign = "LEFT"
            aplot._restrictSize(6.5 * inch, 4 * inch)
            Story.append(aplot)
            os.remove(".utilization.png")

        # Energy chart
        if True:
            labels = []
            min_energy = []
            mean_energy = []
            max_energy = []
            for gpu in range(self.numGPUs):
                labels.append("Card %i" % gpu)
                min_energy.append(np.min(self.energyStats_kwh[gpu]))
                max_energy.append(np.max(self.energyStats_kwh[gpu]))
                mean_energy.append(np.mean(self.energyStats_kwh[gpu]))

            # build max/min bars
            emax = []
            emin = []
            for gpu in range(self.numGPUs):
                emin.append(mean_energy[gpu] - min_energy[gpu])
                emax.append(max_energy[gpu] - mean_energy[gpu])

            #            plt.figure(figsize=(6.,2))
            plt.figure(figsize=(9, 2.5))
            plt.barh(
                labels,
                mean_energy,
                align="center",
                height=0.75,
                edgecolor="black",
                color="grey",
                alpha=0.6,
                xerr=[emin, emax],
                capsize=5,
                error_kw=dict(lw=1, capthick=2),
            )
            plt.title("GPU Energy Consumed - Average (min/max) across All %i Hosts" % len(self.hosts))
            # ,fontsize=8)
            plt.xlabel("Energy (kWH)")
            plt.grid()
            # plt.gca().tick_params(axis='both',labelsize=8)
            plt.savefig(".energy.png", dpi=150, bbox_inches="tight")
            plt.close()

            aplot = Image(".energy.png")
            aplot.hAlign = "LEFT"
            aplot._restrictSize(6.5 * inch, 3 * inch)
            Story.append(aplot)
            os.remove(".energy.png")

        Story.append(Spacer(1, 0.2 * inch))
        Story.append(HRFlowable(width="100%", thickness=1))

        # Multi-node distributions
        if False:
            Story.append(Spacer(1, 0.2 * inch))
            ptext = """<strong>Multi-node Distribution</strong>"""
            Story.append(Paragraph(ptext, normal))
            Story.append(Spacer(1, 0.2 * inch))

            # mean gpu utilization
            allgpus = []
            for gpu in range(self.numGPUs):
                allgpus += self.mean_util_per_gpu[gpu]
            allgpus.sort(reverse=True)
            plt.figure(figsize=(9, 2.5))
            plt.plot(allgpus, "o", markersize=2, fillstyle="none")
            # linewidth=0.8)
            plt.grid()
            plt.xlabel("GPU #")
            plt.ylabel("GPU Utilization (%)")
            plt.ylim(0, 100)
            plt.title("Individual GPU Utilizations Averaged over Job Duration")
            plt.savefig(".distribution.png", dpi=150, bbox_inches="tight")
            plt.close()
            aplot = Image(".distribution.png")
            aplot.hAlign = "LEFT"
            aplot._restrictSize(6.5 * inch, 4 * inch)
            Story.append(aplot)
            os.remove(".distribution.png")

            Story.append(Spacer(1, 0.2 * inch))
            Story.append(HRFlowable(width="100%", thickness=1))

        footerStyle = ParagraphStyle(
            "footer",
            fontSize=8,
            parent=styles["Normal"],
        )

        ptext = """Query interval = %i secs""" % self.interval
        Story.append(Paragraph(ptext, footerStyle))
        ptext = """Query execution time = %.1f secs""" % (timeit.default_timer() - self.timer_start)
        Story.append(Paragraph(ptext, footerStyle))
        # version = self.version
        # if self.sha != "Unknown":
        #     version += " (%s)" % self.sha
        ptext = """Version = %s""" % self.version
        Story.append(Paragraph(ptext, footerStyle))
        Story.append(HRFlowable(width="100%", thickness=1))

        # Build the .pdf
        doc.build(Story)

        return

    def export_metrics(self, output_file, metrics, pivot_labels):
        """Export time series for given metrics as a CSV file.

        Organize columns hierarchically, aligning timestamps and allowing
        access to values by the labels provided as "pivot_labels". For
        example, for ROCm metrics we use the metric -> instance -> card
        hierarchy as follows:
         | metric              | rocm_utilization_percentage   |
         | instance            | node01        | node02        |
         | card                | 0     | 1     | 0     | 1     |
         | timestamp           |       |       |       |       |
         | ------------------- | ----- | ----- | ----- | ----- |
         | 2025-01-01 10:00:00 | 100.0 | 100.0 | 100.0 | 100.0 |
         | 2025-01-01 10:00:00 | 100.0 | 100.0 | 100.0 | 100.0 |
         | ...                 | ...   | ...   | ...   | ...   |

        Args:
            output_file (string): path to output CSV file
            metrics (list): list of metrics to export
            pivot_labels (list): list of labels to use for hierarchical indexing
        """

        index = ["timestamp"] + pivot_labels

        metric_dfs = []
        for metric in metrics:
            query = "%s * on (instance) group_left() rmsjob_info{$job,$step}" % (metric)
            metric_data = self.query_job_range(query)

            if len(metric_data) == 0:
                continue

            metric_df = MetricRangeDataFrame(metric_data)

            # Discard additional labels some metrics may have, like "location"
            # in "rocm_temperature_celsius".
            metric_df = metric_df.reset_index()
            extra_labels = set(metric_df.columns) - set(index) - {"value"}
            for label in extra_labels:
                metric_df = metric_df.drop(label, axis=1)

            metric_df = metric_df.rename(columns={"value": metric})
            metric_df = metric_df.set_index(index, drop=True)
            metric_df = metric_df.unstack(pivot_labels)
            metric_df.columns = metric_df.columns.set_names("metric", level=0)
            metric_df = metric_df.sort_index(axis=1)

            metric_dfs.append(metric_df)

        if len(metric_dfs) > 0:
            df = pandas.concat(metric_dfs, axis=1)
            df.to_csv(output_file)

    def export(self, export_path):
        export_prefix = "omnistat-"

        # Map files to be generated for different subsets of metrics. Values
        # are tuples containing 1) a list of metrics, and 2) a list of labels
        # to be used for hierarchical indexing.
        exports = {
            "rocm": (
                [x["metric"] for x in self.metrics],
                ["instance", "card"],
            ),
            "network": (
                ["omnistat_network_rx_bytes", "omnistat_network_tx_bytes"],
                ["instance", "device_class", "interface"],
            ),
            "rocprofiler": (
                ["omnistat_rocprofiler"],
                ["instance", "card", "counter"],
            ),
        }

        for name, (metrics, labels) in exports.items():
            export_file = f"{export_path}/{export_prefix}{name}.csv"
            self.export_metrics(export_file, metrics, labels)


def main():

    # command line args (jobID is required)
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="print version info and exit", action="store_true")
    parser.add_argument("--job", help="jobId to query")
    parser.add_argument("--step", help="SLURM job step to restrict query interval")
    parser.add_argument("--interval", type=float, help="sampling interval in secs (default=30)", default=30)
    parser.add_argument("--output", help="location for stdout report")
    parser.add_argument("--configfile", type=str, help="runtime config file", default=None)
    parser.add_argument("--pdf", help="generate PDF report")
    parser.add_argument("--export", help="export metric time-series in CSV format", nargs="?", default=None, const="./")
    args = parser.parse_args()

    # logger config
    logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stdout)

    versionData = utils.getVersion()
    if args.version:
        utils.displayVersion(versionData)
        sys.exit(0)

    if not args.job:
        utils.error("The following arguments are required: --job")

    query = queryMetrics(versionData)
    query.set_options(jobID=args.job, output_file=args.output, pdf=args.pdf, interval=args.interval, step=args.step)
    query.read_config(args.configfile)
    query.setup()
    query.gather_data(saveTimeSeries=True)
    query.generate_report_card()

    if args.pdf:
        query.dumpFile(args.pdf)

    if args.export:
        export_path = Path(args.export)
        if export_path.exists() and not export_path.is_dir():
            utils.error(f"--export argument should be be an existing or new directory directory")

        export_path.mkdir(exist_ok=True)
        query.export(export_path)


if __name__ == "__main__":
    main()
