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

"""PM counter monitoring

Scans telmetry in /sys/cray/pm_counters for compute node power-related data.
"""

import json
import logging
import os
import platform
import re
import sys
from pathlib import Path

from prometheus_client import Gauge

import omnistat.utils as utils
from omnistat.collector_base import Collector


class PM_COUNTERS(Collector):
    def __init__(self, annotations=False, jobDetection=None):
        logging.debug("Initializing pm_counter data collector")

        self.__prefix = "omnistat_pmcounter_"
        self.__pm_counter_dir = "/sys/cray/pm_counters"
        self.__skipnames = ["power_cap","startup","freshness","raw_scan_hz","version","generation","_temp"]
        self.__gpumetrics = ["accel"]
        # metric data structure for host oriented metrics
        # --> format: (gauge metric, filepath of source data)
        self.__pm_files_gpu = []
        # metric data structure for gpu oriented
        # --> format: (gauge metric, filepath of source data, gpuindex)
        self.__pm_files_host = []


    def registerMetrics(self):
        """Register metrics of interest"""

        definedMetrics = {}

        logging.info("collector_pm_counters: scanning files in %s" % self.__pm_counter_dir)
        for file in Path(self.__pm_counter_dir).iterdir():
            logging.debug("Examining PM counter filename: %s" % file)
            if any(name in str(file) for name in self.__skipnames):
                logging.debug("--> Skipping PM file: %s" % file)
            else:
                for gpumetric in self.__gpumetrics:
                    pattern = fr"^({gpumetric})(\d+)(_.*)$"
                    match = re.match(pattern,file.name)
                    if match:
                        metric_name = match.group(1) + match.group(3)
                        gpu_id = int(match.group(2))
                        if metric_name in definedMetrics:
                            gauge = definedMetrics[metric_name]
                        else:
                            gauge = Gauge(self.__prefix + metric_name, metric_name, labelnames=["card"])
                            definedMetrics[metric_name] = gauge
                            logging.info("--> [Registered] %s (gauge)" % (self.__prefix + metric_name))
                            
                        metric_entry = (gauge,str(file),gpu_id)                            
                        self.__pm_files_gpu.append(metric_entry)

                    else:
                        metric_name = file.name
                        gauge = Gauge(self.__prefix + metric_name, metric_name)
                        metric_entry = (gauge, str(file))
                        self.__pm_files_host.append(metric_entry)
                        logging.info("--> [registered] %s (gauge)" % self.__prefix + metric_name)                        

    def updateMetrics(self):
        """Update registered metrics of interest"""

        # Host-level data...
        for entry in self.__pm_files_host:
            gaugeMetric = entry[0]
            filePath = entry[1]
            try:
                with open(filePath,"r") as f:
                    data = f.readline().strip().split()
                    gaugeMetric.set(float(data[0]))
            except:
                pass

        # GPU data...
        for entry in self.__pm_files_gpu:
            gaugeMetric = entry[0]
            filePath = entry[1]
            gpuIndex = entry[2]
            try:
                with open(filePath,"r") as f:
                    data = f.readline().strip().split()
                    gaugeMetric.labels(card=gpuIndex).set(data[0])

            except:
                pass            

        return

