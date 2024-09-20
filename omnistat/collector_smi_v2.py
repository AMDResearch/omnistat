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

"""amd-smi data collector

Implements a number of prometheus gauge metrics based on GPU data collected from
amd-smi library.  The ROCm runtime must be pre-installed to use this data
collector. This data collector gathers statistics on a per GPU basis and exposes
metrics with "amdsmi_{metric_name}" with labels for each GPU number. The following example highlights example metrics:

amdsmi_vram_total_bytes{card="0"} 3.4342961152e+010
amdsmi_temperature_celsius{card="0"} 42.0
amdsmi_utilization_percentage{card="0"} 0.0
amdsmi_vram_used_percentage{card="0"} 0.0
amdsmi_average_socket_power_watts{card="0"} 35.0
amdsmi_mlck_clock_mhz{card="0"} 1200.0
amdsmi_slck_clock_mhz{card="0"} 300.0
"""

import logging
import packaging.version
import statistics
import sys
import amdsmi as smi
from omnistat.collector_base import Collector
from prometheus_client import Gauge
from omnistat.utils import convert_bdf_to_gpuid, gpu_index_mapping_based_on_bdfs


def get_gpu_metrics(device):
    result = smi.amdsmi_get_gpu_metrics_info(device)
    for k, v in result.items():
        if type(v) is str:
            # Filter 'N/A' values introduced by rocm 6.1
            result[k] = 0
            continue
        elif type(v) is bool:
            # Filter boolean values introduced by rocm 6.1
            result[k] = 0
            continue
        # Average of list values
        elif type(v) is list:
            v = [x for x in v if type(x) not in [bool, str]]
            if not v:
                # Filter empty lists
                result[k] = 0
                continue
            v = int(statistics.mean(v))
            result[k] = v
        # Bigger than signed 64-bit integer
        if v >= 9223372036854775807 or v <= -9223372036854775808:
            result[k] = 0
    return result


def check_min_version(minVersion):
    localVer = smi.amdsmi_get_lib_version()
    localVerString = ".".join([str(localVer["year"]), str(localVer["major"]), str(localVer["minor"])])
    vmin = packaging.version.Version(minVersion)
    vloc = packaging.version.Version(localVerString)
    if vloc < vmin:
        logging.error("")
        logging.error("ERROR: Minimum amdsmi version not met.")
        logging.error("--> Detected version = %s (>= %s required)" % (vloc, vmin))
        logging.error("")
        sys.exit(4)
    else:
        logging.info("--> library version = %s" % vloc)


class AMDSMI(Collector):
    def __init__(self):
        logging.debug("Initializing AMD SMI data collector")
        self.__prefix = "amdsmi_"
        smi.amdsmi_init()
        logging.info("AMD SMI library API initialized")
        self.__num_gpus = 0
        self.__devices = []
        self.__GPUMetrics = {}
        self.__metricMapping = {}
        self.__indexMapping = {}
        self.__dumpMappedMetricsOnly = False # TODO should be a config option
        # verify minimum version met
        check_min_version("23.4.0") # Rocm 6.0.2

    def registerMetrics(self):
        """Query number of devices and register metrics of interest"""

        devices = smi.amdsmi_get_processor_handles()
        self.__devices = devices
        self.__num_gpus = len(devices)
        logging.debug(f"Number of devices = {self.__num_gpus}")

        # Register/set metrics that we do not expect to change

        # number of GPUs
        numGPUs_metric = Gauge(
            self.__prefix + "num_gpus",
            "# of GPUS available on host",
        )
        numGPUs_metric.set(self.__num_gpus)

        # determine GPU index mapping (i.e. map kfd indices used by SMI lib to that of HIP_VISIBLE_DEVICES)
        bdfMapping = {}
        for index, device in enumerate(self.__devices):
            bdf = smi.amdsmi_get_gpu_device_bdf(device)
            bdf_id = smi.amdsmi_get_gpu_bdf_id(device)
            bdfMapping[index] = convert_bdf_to_gpuid(bdf)
        self.__indexMapping = gpu_index_mapping_based_on_bdfs(bdfMapping, self.__num_gpus)

        # Define mapping from amdsmi variable names to omnistat metric, incuding units where appropriate
        self.__metricMapping = {
            # core GPU metric definitions
            "average_gfx_activity": "utilization_percentage",
            "vram_total": "vram_total_bytes",
            "average_socket_power": "average_socket_power_watts",
            "temperature_edge": "temperature_celsius",
            "current_gfxclks": "sclk_clock_mhz",
            "average_uclk_frequency": "mclk_clock_mhz",
        }

        # Register memory related metrics
        self.__GPUMetrics["vram_total_bytes"] = Gauge(
            self.__prefix + "vram_total_bytes", "VRAM Memory in Use (%)", labelnames=["card"]
        )
        self.__GPUMetrics["vram_used_percentage"] = Gauge(
            self.__prefix + "vram_used_percentage", "VRAM Memory in Use (%)", labelnames=["card"]
        )

        # Register remaining metrics of interest available from get_gpu_metrics()
        for idx, device in enumerate(self.__devices):

            metrics = get_gpu_metrics(device)

            for metric, value in metrics.items():
                old_metric = ""
                if self.__metricMapping.get(metric):
                    old_metric = metric
                    metric = self.__metricMapping.get(metric)
                elif self.__dumpMappedMetricsOnly is True:
                    continue
                metric_name = self.__prefix + metric

                # add Gauge metric only once
                if metric_name not in self.__GPUMetrics.keys():
                    self.__GPUMetrics[metric_name] = Gauge(metric_name, f"{metric}", labelnames=["card"])

                # temp workaround to allow support for all metric names
                if old_metric and old_metric not in self.__GPUMetrics.keys():
                    self.__GPUMetrics[metric_name].labels(card=idx).set(value)


        return

    def updateMetrics(self):
        self.collect_data_incremental()
        return

    def collect_data_incremental(self):
        for idx, device in enumerate(self.__devices):

            # map GPU index
            cardId = self.__indexMapping[idx]

            # gpu memory-related stats
            device_total_vram = smi.amdsmi_get_gpu_memory_total(device, smi.AmdSmiMemoryType.VRAM)
            self.__GPUMetrics["vram_total_bytes"].labels(card=cardId).set(device_total_vram)
            vram_used_bytes = smi.amdsmi_get_gpu_memory_usage(device, smi.AmdSmiMemoryType.VRAM)
            percentage = round(100.0 * vram_used_bytes / device_total_vram, 4)
            self.__GPUMetrics["vram_used_percentage"].labels(card=cardId).set(percentage)

            # other stats available via get_gpu_metrics
            metrics = get_gpu_metrics(device)
            for metric, value in metrics.items():
                if self.__metricMapping.get(metric):
                    metric = self.__metricMapping.get(metric)
                elif self.__dumpMappedMetricsOnly is True:
                    continue
                metric = self.__GPUMetrics[self.__prefix + metric]
                # Set metric
                metric.labels(card=cardId).set(value)
        return
