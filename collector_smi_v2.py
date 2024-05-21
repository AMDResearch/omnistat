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
metrics with a "card.*_rocm prefix". The following example highlights example
metrics for card 0:

card0_rocm_temp_die_edge 36.0
card0_rocm_avg_pwr 30.0
card0_rocm_utilization 0.0
card0_rocm_vram_total 3.4342961152e+010
card0_rocm_vram_used 7.028736e+06
card0_rocm_sclk_clock_mhz 300.0
card0_rocm_mclk_clock_mhz 1200.0
"""

import ctypes
import logging
import os
from collector_base import Collector
from prometheus_client import Gauge, generate_latest, CollectorRegistry

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
    def __init__(self,rocm_smi_binary=None):
        logging.debug("Initializing ROCm SMI data collector")
        self.__prefix = "rocm_"

        # load smi runtime
        rocm_lib = "/opt/rocm/lib"
        self.__libsmi = ctypes.CDLL(rocm_lib + "/librocm_smi64.so")
        logging.info("Runtime library loaded")

        # initialize smi library
        ret_init = self.__libsmi.rsmi_init(0)
        assert(ret_init == 0)
        logging.info("SMI library API initialized")

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
        #numDevices = 0
        ret = self.__libsmi.rsmi_num_monitor_devices(ctypes.byref(numDevices))
        # ret = proto_devices(ctypes.byref(numDevices))
        logging.debug("Number of devices = %i" % numDevices.value)

        # register number of GPUs
        numGPUs_metric = Gauge(
            self.__prefix + "num_gpus", "# of GPUS available on host"
        )
        numGPUs_metric.set(numDevices.value)
        self.__num_gpus = numDevices.value

        # register desired metrics (per device)
        for i in range(self.__num_gpus):
            gpu = "card" + str(i)
            # init storage per gpu
            self.__GPUmetrics[gpu] = {}

            # temperature
            self.registerGPUMetric(gpu, self.__prefix + "temp_die_edge", "gauge", "Temperature (Sensor edge) (C)")
            # power
            self.registerGPUMetric(gpu, self.__prefix + "avg_pwr", "gauge", "Average Graphics Package Power (W)")
            # clock speeds
            self.registerGPUMetric(gpu, self.__prefix + "sclk_clock_mhz", "gauge", "sclk clock speed (Mhz)")
            self.registerGPUMetric(gpu, self.__prefix + "mclk_clock_mhz", "gauge", "mclk clock speed (Mhz)")
            # memory
            self.registerGPUMetric(gpu, self.__prefix + "vram_total", "gauge", "VRAM Total Memory (B)")
            self.registerGPUMetric(gpu, self.__prefix + "vram_used", "gauge", "VRAM Total Used Memory (B)")
            # utilization
            self.registerGPUMetric(gpu, self.__prefix + "utilization","gauge","GPU use (%)")
        
        return

    def updateMetrics(self):
        self.collect_data_incremental()
        return

    # --------------------------------------------------------------------------------------
    # Additional custom methods unique to this collector

    def registerGPUMetric(self, gpu, name, type, description):
        # encode gpu in name for uniqueness
        metricName = name
        if metricName in self.__GPUmetrics[gpu]:
            logging.error(
                "Ignoring duplicate metric name addition: %s (gpu=%s)" % (name, gpu)
            )
            return

        if type == "gauge":
            if metricName not in self.__GPUmetrics:
                self.__GPUmetrics[metricName] = "1"
            else:
                return
            self.__GPUmetrics[gpu][metricName] = Gauge(metricName, description, labelnames=['card'])
            logging.info(
                "  --> [registered] %s -> %s (gauge)" % (metricName, description)
            )
            # # Omri Test
            # self.__GPUmetrics[gpu][metricName + "_omri"] = Gauge(name, description, labelnames=['card'])
            # logging.info(
            #     "  --> [registered] %s -> %s (gauge)" % (metricName + "_omri", description)
            # )
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
        freq_system_clock = 0   # 0=RSMI_CLK_TYPE_SYS
        freq_mem_clock = 4      # 4=RSMI_CLK_TYPE_MEM
        vram_total = ctypes.c_uint64(0)
        vram_used  = ctypes.c_uint64(0)
        utilization = ctypes.c_uint32(0)

        for i in range(self.__num_gpus):
            
            gpu = "card" + str(i)
            device = ctypes.c_uint32(i)

            #--
            # temperature [millidegrees Celcius, converted to degrees Celcius]
            metric = self.__prefix + "temp_die_edge"
            ret = self.__libsmi.rsmi_dev_temp_metric_get(device,
                                                         temp_location,
                                                         temp_metric,
                                                         ctypes.byref(temperature))
            self.__GPUmetrics[gpu][metric].labels(card=gpu).set(temperature.value / 1000.0)

            #--
            # average power [micro Watts, converted to Watts]
            metric = self.__prefix + "avg_pwr"
            ret = self.__libsmi.rsmi_dev_power_ave_get(device, 0, ctypes.byref(power))
            self.__GPUmetrics[gpu][metric].labels(card=gpu).set(power.value / 1000000.0)

            #--
            # clock speeds [Hz, converted to megaHz]
            metric = self.__prefix + "sclk_clock_mhz"
            ret = self.__libsmi.rsmi_dev_gpu_clk_freq_get(device,freq_system_clock, ctypes.byref(freq))
            self.__GPUmetrics[gpu][metric].labels(card=gpu).set(freq.frequency[freq.current] / 1000000.0)
            
            metric = self.__prefix + "mclk_clock_mhz"
            ret = self.__libsmi.rsmi_dev_gpu_clk_freq_get(device,freq_mem_clock, ctypes.byref(freq))
            self.__GPUmetrics[gpu][metric].labels(card=gpu).set(freq.frequency[freq.current] / 1000000.0)

            #--
            # memory [Hz, converted to megaHz]
            metric = self.__prefix + "vram_total"
            ret = self.__libsmi.rsmi_dev_memory_total_get(device,0x0,ctypes.byref(vram_used))
            self.__GPUmetrics[gpu][metric].labels(card=gpu).set(vram_used.value)

            metric = self.__prefix + "vram_used"
            ret = self.__libsmi.rsmi_dev_memory_usage_get(device,0x0,ctypes.byref(vram_total))
            self.__GPUmetrics[gpu][metric].labels(card=gpu).set(vram_total.value)

            #--
            # utilization
            metric = self.__prefix + "utilization"
            ret = self.__libsmi.rsmi_dev_busy_percent_get(device,ctypes.byref(utilization))
            self.__GPUmetrics[gpu][metric].labels(card=gpu).set(utilization.value)

            # # util omri
            # metric = self.__prefix + "utilization" + "_omri"
            # ret = self.__libsmi.rsmi_dev_busy_percent_get(device,ctypes.byref(utilization))
            # # self.__GPUmetrics[gpu][metric].set(utilization.value)
            # self.__GPUmetrics[gpu][metric].labels(card=gpu).set(utilization.value)


        return
