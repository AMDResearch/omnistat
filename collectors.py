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

# Prometheus data collector for HPC systems.
#
# Custom collector(s) - defines required methods for all metric collectors
# implemented as a child class.
# --

import sys
import utils
import json
import logging
import os
import platform
from collector_base import Collector
from prometheus_client import Gauge, generate_latest, CollectorRegistry


class ROCMSMI(Collector):
    def __init__(self):
        logging.debug("Initializing ROCm SMI data collector")
        self.__prefix = "rocm_"

        # setup rocm-smi path
        command = utils.resolvePath("rocm-smi", "ROCM_SMI_PATH")
        # command-line flags for use with rocm-smi to obtained desired metrics
        flags = "-P -c -u -f -t --showmeminfo vram --json"
        # cache query command with options
        self.__rocm_smi_query = [command] + flags.split()

        # list of desired metrics to query: (prometheus_metric_name -> rocm-smi-key)
        self.__rocm_smi_metrics = {
            self.__prefix + "temp_die_edge": "Temperature (Sensor edge) (C)",
            self.__prefix + "avg_pwr": "Average Graphics Package Power (W)",
            self.__prefix + "utilization": "GPU use (%)",
            self.__prefix + "vram_total": "VRAM Total Memory (B)",
            self.__prefix + "vram_used": "VRAM Total Used Memory (B)",
            self.__prefix + "sclk_clock_mhz": "sclk clock speed:",
            self.__prefix + "mclk_clock_mhz": "mclk clock speed:",
        }

        logging.debug("rocm_smi_exec = %s" % self.__rocm_smi_query)

        self.__GPUmetrics = {}

    # --------------------------------------------------------------------------------------
    # Required child methods

    def registerMetrics(self):
        """Run rocm-smi and register metrics of interest"""

        data = utils.runShellCommand(self.__rocm_smi_query, exit_on_error=True)
        data = json.loads(data.stdout)

        # register number of GPUs
        numGPUs_metric = Gauge(
            self.__prefix + "num_gpus", "# of GPUS available on host"
        )
        numGPUs_metric.set(len(data))

        for gpu in data:
            logging.debug("%s: gpu detected" % gpu)
            # init storage per gpu
            self.__GPUmetrics[gpu] = {}

            # look for matching metrics and register
            for metric in self.__rocm_smi_metrics:
                rocmName = self.__rocm_smi_metrics[metric]
                if rocmName in data[gpu]:
                    self.registerGPUMetric(gpu, metric, "gauge", rocmName)
                else:
                    logging.info("   --> desired metric [%s] not available" % rocmName)
            # also highlight metrics not being used
            for key in data[gpu]:
                if key not in self.__rocm_smi_metrics.values():
                    logging.info("  --> [  skipping] %s" % key)
        return

    def updateMetrics(self):
        self.collect_data_incremental()
        return

    # --------------------------------------------------------------------------------------
    # Additional custom methods unique to this collector

    def registerGPUMetric(self, gpu, name, type, description):
        # encode gpu in name for uniqueness
        metricName = gpu + "_" + name
        if metricName in self.__GPUmetrics[gpu]:
            logging.error(
                "Ignoring duplicate metric name addition: %s (gpu=%s)" % (name, gpu)
            )
            return
        if type == "gauge":
            self.__GPUmetrics[gpu][metricName] = Gauge(metricName, description)
            logging.info(
                "  --> [registered] %s -> %s (gauge)" % (metricName, description)
            )
        else:
            logging.error("Ignoring unknown metric type -> %s" % type)
        return

    def collect_data_incremental(self):
        # ---
        # Collect and parse latest GPU metrics from rocm-smi
        # ---
        data = utils.runShellCommand(self.__rocm_smi_query)
        try:
            data = json.loads(data.stdout)
        except:
            logging.error("Unable to parse json data from rocm-smi querry")
            logging.debug("stdout: %s" % data.stderr)
            logging.debug("stderr: %s" % data.stderr)
            return

        for gpu in self.__GPUmetrics:
            for metric in self.__GPUmetrics[gpu]:
                metricName = metric.removeprefix(gpu + "_")
                rocmName = self.__rocm_smi_metrics[metricName]
                if rocmName in data[gpu]:
                    value = data[gpu][rocmName]
                    if rocmName.endswith("clock speed:"):
                        # values need to be parsed to access data, they look like '(300Mhz)'
                        value = value[1:].rstrip("Mhz)")
                    self.__GPUmetrics[gpu][metric].set(value)
                    logging.debug("updated: %s = %s" % (metric, value))
        return


# SLURM Job collector
class SlurmJob(Collector):
    def __init__(self):
        logging.debug("Initializing SlurmJob data collector")
        self.__prefix = "slurmjob_"

        # setup slurm binary path
        command = utils.resolvePath("squeue", "SLURM_PATH")
        # command-line flags for use with squeue to obtained desired metrics
        hostname = platform.node().split(".", 1)[0]
        #flags = "-w " + hostname + " -h  --format=%i,%u,%P,%D,%C"
        flags = "-w " + hostname + " -h  --Format=JobID::,UserName::,Partition::,NumNodes::,BatchFlag"
        # cache query command with options
        self.__squeue_query = [command] + flags.split()

        logging.debug("sqeueue_exec = %s" % self.__squeue_query)

        self.__SLURMmetrics = {}

    def registerMetrics(self):
        """Register metrics of interest"""

        # alternate approach - define an info metric
        # (https://ypereirareis.github.io/blog/2020/02/21/how-to-join-prometheus-metrics-by-label-with-promql/)
        labels = ["jobid", "user", "partition", "nodes","batchflag"]
        self.__SLURMmetrics["info"] = Gauge(
            self.__prefix + "info", "SLURM job id", labels
        )

        # metric to support user annotations
        self.__SLURMmetrics["annotations"] = Gauge(
            self.__prefix + "annotations", "User job annotations", ["marker","jobid"]
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
                batchflag=results[4]
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
                jobid="", user="", partition="", nodes="",batchflag=""
            ).set(1)

        return
