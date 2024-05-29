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
from utils import GPU_MAPPING_ORDER
from amdsmi import amdsmi_init, amdsmi_get_processor_handles, amdsmi_get_gpu_process_list, amdsmi_get_gpu_process_info

def get_gpu_processes(device):
    processes = amdsmi_get_gpu_process_list(device)

    result = []
    for p in processes:
        try:
            p = amdsmi_get_gpu_process_info(device, p)
        except:
            # Catch all for unsupported rocm version for process info
            return result
        # Ignore the Python process itself for the reading
        if p['name'] == 'python3' and (p['mem'] == 4096 or p["memory_usage"]["vram_mem"] == 12288):
            continue
        result.append(p)
    return result


class AMDSMIProcess(Collector):
    def __init__(self):
        logging.debug("Initializing AMD SMI Process data collector")
        self.__prefix = "amdsmi_process_"
        amdsmi_init()
        logging.info("AMD SMI library API initialized for Process information collection")
        self.metric_vram = None
        self.metric_compute = None
        self.devices = []
        self.process_metrics = {}
        self.c = 0

    def registerMetrics(self):
        """Query number of devices and register metrics of interest"""

        devices = amdsmi_get_processor_handles()
        self.devices = devices
        metric_vram = Gauge(
            f"{self.__prefix}vram",
            f"{self.__prefix}vram",
            labelnames=["card", "name", "pid"],
        )
        metric_compute = Gauge(
            f"{self.__prefix}compute",
            f"{self.__prefix}compute",
            labelnames=["card", "name", "pid"],
        )
        self.metric_vram = metric_vram
        self.metric_compute = metric_compute
        self.updateMetrics()
        return

    def updateMetrics(self):

        self.collect_data_incremental()
        # Remove old labels for process not currently running
        for metric, counter in self.process_metrics.items():
            if counter < self.c:
                # catch edge case for multiple metrics with same name
                try:
                    self.metric_vram.remove(metric[0], metric[1], metric[2])
                except:
                    pass
                try:
                    self.metric_compute.remove(metric[0], metric[1], metric[2])
                except:
                    pass

        return

    def collect_data_incremental(self):
        self.c += 1
        for idx, device in enumerate(self.devices):

            processes = get_gpu_processes(device)

            for process in processes:
                metric_tuple = (str(GPU_MAPPING_ORDER[idx]), process["name"], str(process["pid"]))

                self.process_metrics[metric_tuple] = self.c
                self.metric_vram.labels(
                    card=str(GPU_MAPPING_ORDER[idx]),
                    name=str(process["name"]),
                    pid=str(process["pid"]),
                ).set(process["memory_usage"]["vram_mem"])
                self.metric_compute.labels(
                    card=str(GPU_MAPPING_ORDER[idx]),
                    name=str(process["name"]),
                    pid=str(process["pid"]),
                ).set(process["engine_usage"]["gfx"])

        return
