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

amdsmi_temp_die_edge 36.0
amdsmi_avg_pwr 30.0
amdsmi_utilization 0.0
amdsmi_vram_total 3.4342961152e+010
amdsmi_vram_used 7.028736e+06
amdsmi_sclk_clock_mhz 300.0
amdsmi_mclk_clock_mhz 1200.0
"""

import logging
from collector_base import Collector
from prometheus_client import Gauge
import statistics
from utils import GPU_MAPPING_ORDER
from amdsmi import (amdsmi_init, amdsmi_get_processor_handles, amdsmi_get_gpu_metrics_info, amdsmi_get_gpu_memory_total,
                    AmdSmiMemoryType)


def get_gpu_metrics(device):
    result = amdsmi_get_gpu_metrics_info(device)
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


class AMDSMI(Collector):
    def __init__(self):
        logging.debug("Initializing AMD SMI data collector")
        self.__prefix = "amdsmi_"
        amdsmi_init()
        logging.info("AMD SMI library API initialized")
        self.num_gpus = 0
        self.devices = []
        self.GPUMetrics = {}

    def registerMetrics(self):
        """Query number of devices and register metrics of interest"""

        devices = amdsmi_get_processor_handles()
        self.devices = devices
        self.num_gpus = len(devices)
        logging.debug(f"Number of devices = {self.num_gpus}")

        # register number of GPUs
        numGPUs_metric = Gauge(
            self.__prefix + "num_gpus", "# of GPUS available on host",
        )
        numGPUs_metric.set(self.num_gpus)

        # Register Total VRAM for GPU metric
        total_vram_metric = Gauge(
            self.__prefix + "total_vram", "Total VRAM available on GPU", labelnames=["card"])

        for idx, device in enumerate(self.devices):

            device_total_vram = amdsmi_get_gpu_memory_total(device, AmdSmiMemoryType.VRAM)
            total_vram_metric.labels(card=str(idx)).set(device_total_vram)

            metrics = get_gpu_metrics(device)
            for k, v in metrics.items():
                metric_name = self.__prefix + k
                if metric_name not in self.GPUMetrics.keys():
                    # add Gauge Metric only once
                    metric = Gauge(
                        self.__prefix + k,
                        f"{k}",
                        labelnames=["card"],
                    )
                    self.GPUMetrics[metric_name] = metric
                else:
                    metric = self.GPUMetrics[metric_name]
                # Set metric once per GPU
                metric.labels(card=str(idx)).set(v)
                
        return

    def updateMetrics(self):
        self.collect_data_incremental()
        return

    def collect_data_incremental(self):
        for idx, device in enumerate(self.devices):
            metrics = get_gpu_metrics(device)
            for k, v in metrics.items():
                metric_name = self.__prefix + k
                metric = self.GPUMetrics[metric_name]
                # Set metric
                metric.labels(card=str(GPU_MAPPING_ORDER[idx])).set(v)
        return

