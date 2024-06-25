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

"""ROCM-smi data collector

Implements a number of prometheus gauge metrics based on GPU data collected from
rocm smi library.  The ROCm runtime must be pre-installed to use this data
collector. This data collector gathers statistics on a per GPU basis and exposes
metrics with a "rocm" prefix with individual cards denotes by labels. The
following example highlights example metrics for card 0:

rocm_temperature_edge_celsius{card="0"} 41.0
rocm_average_socket_power_watts{card="0"} 35.0
rocm_sclk_clock_mhz{card="0"} 1502.0
rocm_mclk_clock_mhz{card="0"} 1200.0
rocm_vram_total_bytes{card="0"} 3.4342961152e+010
rocm_vram_used_percentage{card="0"} 0.0198
rocm_utilization_percentage{card="0"} 0.0
"""

import ctypes
import logging
import os
import sys
from prometheus_client import Gauge, generate_latest, CollectorRegistry

from omniwatch.collector_base import Collector

# lifted from rsmiBindings.py
RSMI_MAX_NUM_FREQUENCIES = 32
class rsmi_frequencies_t(ctypes.Structure):
    _fields_ = [('num_supported', ctypes.c_int32),
                ('current', ctypes.c_uint32),
                ('frequency', ctypes.c_uint64 * RSMI_MAX_NUM_FREQUENCIES)]

rsmi_clk_names_dict = {'sclk': 0x0, 'fclk': 0x1, 'dcefclk': 0x2,\
                       'socclk': 0x3, 'mclk': 0x4}

#--

class ROCMSMI(Collector):
    def __init__(self,rocm_path="/opt/rocm"):
        logging.debug("Initializing ROCm SMI data collector")
        self.__prefix = "rocm_"

        # load smi runtime
        smi_lib = rocm_path + "/lib/librocm_smi64.so"
        if os.path.isfile(smi_lib):
            self.__libsmi = ctypes.CDLL(smi_lib)
            logging.info("Runtime library loaded from %s" % smi_lib)

            # initialize smi library
            ret_init = self.__libsmi.rsmi_init(0)
            assert(ret_init == 0)
            logging.info("SMI library API initialized")
        else:
            logging.error("")
            logging.error("ERROR: Unable to load SMI library.")
            logging.error("--> looking for %s" % smi_lib)
            logging.error("--> please verify path and set \"rocm_path\" in runtime config file if necesssary.")
            logging.error("")
            sys.exit(4)

        self.__GPUmetrics = {}

    # --------------------------------------------------------------------------------------
    # Required child methods

    def registerMetrics(self):
        """Query number of devices and register metrics of interest"""
        # proto_devices = self.__libsmi.rsmi_num_monitor_devices
        # # proto_devices.argtypes = [ctypes.byref(ctypes.c_uint32)]
        # # proto_devices.argtype = [ctypes.pointer(ctypes.c_uint32)]
        # # proto_devices.restype = ctypes.c_int
        # # proto_devices = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.byref(ctypes.c_uint32))

        numDevices = ctypes.c_uint32(0)
        ret = self.__libsmi.rsmi_num_monitor_devices(ctypes.byref(numDevices))
        logging.info("Number of GPU devices = %i" % numDevices.value)

        # register number of GPUs
        numGPUs_metric = Gauge(
            self.__prefix + "num_gpus", "# of GPUS available on host"
        )
        numGPUs_metric.set(numDevices.value)
        self.__num_gpus = numDevices.value

        # register desired metric names
        self.__GPUmetrics = {}

        # temperature
        self.registerGPUMetric(self.__prefix + "temperature_edge_celsius", "gauge", "Temperature (Sensor edge) (C)")
        # power
        self.registerGPUMetric(self.__prefix + "average_socket_power_watts", "gauge", "Average Graphics Package Power (W)")
        # clock speeds
        self.registerGPUMetric(self.__prefix + "sclk_clock_mhz", "gauge", "current sclk clock speed (Mhz)")
        self.registerGPUMetric(self.__prefix + "mclk_clock_mhz", "gauge", "current mclk clock speed (Mhz)")
        # memory
        self.registerGPUMetric(self.__prefix + "vram_total_bytes", "gauge", "VRAM Total Memory (B)")
        self.registerGPUMetric(self.__prefix + "vram_used_percentage", "gauge", "VRAM Memory in Use (%)")
        # utilization
        self.registerGPUMetric(self.__prefix + "utilization_percentage","gauge","GPU use (%)")
        
        return

    def updateMetrics(self):
        self.collect_data_incremental()
        return

    # --------------------------------------------------------------------------------------
    # Additional custom methods unique to this collector

    def registerGPUMetric(self, metricName, type, description):
        if metricName in self.__GPUmetrics:
            logging.error(
                "Ignoring duplicate metric name addition: %s" % (name)
            )
            return
        if type == "gauge":
            self.__GPUmetrics[metricName] = Gauge(metricName, description,labelnames=["card"])

            logging.info(
                "--> [registered] %s -> %s (gauge)" % (metricName, description)
            )
        else:
            logging.error("Ignoring unknown metric type -> %s" % type)
        return

    def collect_data_incremental(self):
        # ---
        # Collect and parse latest GPU metrics from rocm SMI library
        # ---

        temperature = ctypes.c_int64(0)
        temp_metric = ctypes.c_int32(0)    # 0=RSMI_TEMP_CURRENT
        temp_location = ctypes.c_int32(0)  # 0=RSMI_TEMP_TYPE_EDGE
        power = ctypes.c_uint64(0)
        freq = rsmi_frequencies_t()
        freq_system_clock = 0     # 0=RSMI_CLK_TYPE_SYS
        freq_mem_clock = 4        # 4=RSMI_CLK_TYPE_MEM
        vram_total = ctypes.c_uint64(0)
        vram_used  = ctypes.c_uint64(0)
        utilization = ctypes.c_uint32(0)

        for i in range(self.__num_gpus):
            
            device = ctypes.c_uint32(i)
            gpuLabel = str(i)

            #--
            # temperature [millidegrees Celcius, converted to degrees Celcius]
            metric = self.__prefix + "temperature_edge_celsius"
            ret = self.__libsmi.rsmi_dev_temp_metric_get(device,
                                                         temp_location,
                                                         temp_metric,
                                                         ctypes.byref(temperature))
            self.__GPUmetrics[metric].labels(card=gpuLabel).set(temperature.value / 1000.0)

            #--
            # average power [micro Watts, converted to Watts]
            metric = self.__prefix + "average_socket_power_watts"
            ret = self.__libsmi.rsmi_dev_power_ave_get(device, 0, ctypes.byref(power))
            self.__GPUmetrics[metric].labels(card=gpuLabel).set(power.value / 1000000.0)

            #--
            # clock speeds [Hz, converted to megaHz]
            metric = self.__prefix + "sclk_clock_mhz"
            ret = self.__libsmi.rsmi_dev_gpu_clk_freq_get(device,freq_system_clock, ctypes.byref(freq))
            self.__GPUmetrics[metric].labels(card=gpuLabel).set(freq.frequency[freq.current] / 1000000.0)
            
            metric = self.__prefix + "mclk_clock_mhz"
            ret = self.__libsmi.rsmi_dev_gpu_clk_freq_get(device,freq_mem_clock, ctypes.byref(freq))
            self.__GPUmetrics[metric].labels(card=gpuLabel).set(freq.frequency[freq.current] / 1000000.0)

            #--
            # gpu memory [total_vram in bytes]
            metric = self.__prefix + "vram_total_bytes"
            ret = self.__libsmi.rsmi_dev_memory_total_get(device,0x0,ctypes.byref(vram_total))
            self.__GPUmetrics[metric].labels(card=gpuLabel).set(vram_total.value)

            metric = self.__prefix + "vram_used_percentage"
            ret = self.__libsmi.rsmi_dev_memory_usage_get(device,0x0,ctypes.byref(vram_used))
            percentage = round(100.0 * vram_used.value / vram_total.value, 4)
            self.__GPUmetrics[metric].labels(card=gpuLabel).set(percentage)

            #--
            # utilization
            metric = self.__prefix + "utilization_percentage"
            ret = self.__libsmi.rsmi_dev_busy_percent_get(device,ctypes.byref(utilization))
            self.__GPUmetrics[metric].labels(card=gpuLabel).set(utilization.value)

        return
