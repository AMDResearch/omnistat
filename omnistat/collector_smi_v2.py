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

"""amd-smi based data collector

Implements a number of prometheus gauge metrics based on GPU data collected from
the amd-smi library interface.  The ROCm runtime must be pre-installed to use this data
collector. This data collector gathers statistics on a per GPU basis and exposes
metrics with "amdsmi_{metric_name}" with labels for each GPU number. The following
example highlights example metrics:

rocm_vram_total_bytes{card="0"} 3.4342961152e+010
rocm_temperature_celsius{card="0",location="edge"} 42.0
rocm_temperature_memory_celsius{card="0",location="hbm_0"} 46.0
rocm_utilization_percentage{card="0"} 0.0
rocm_vram_used_percentage{card="0"} 0.0
rocm_vram_busy_percentage{card="0"} 22.0
rocm_average_socket_power_watts{card="0"} 35.0
rocm_mlck_clock_mhz{card="0"} 1200.0
rocm_slck_clock_mhz{card="0"} 300.0
"""

import logging
import statistics
import sys

import amdsmi as smi
import packaging.version
from prometheus_client import Gauge

from omnistat.collector_base import Collector
from omnistat.utils import gpu_index_mapping_based_on_guids


def check_min_version(minVersion):
    localVer = smi.amdsmi_get_lib_version()
    # deal with evolving API
    if "year" in localVer:
        localVerString = ".".join([str(localVer["year"]), str(localVer["major"]), str(localVer["minor"])])
    elif "major" in localVer and "release" in localVer:
        localVerString = ".".join([str(localVer["major"]), str(localVer["minor"]), str(localVer["release"])])
    else:
        logging.error("ERROR: Unable to determine amdsmi library version")
        sys.exit(4)
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


def is_positive_int(s):
    try:
        return int(s) > 0
    except:
        return False


class AMDSMI(Collector):
    def __init__(self, runtimeConfig=None):
        logging.debug("Initializing AMD SMI data collector")
        self.__prefix = "rocm_"
        self.__schema = 1.0
        smi.amdsmi_init()
        logging.info("AMD SMI library API initialized")
        self.__num_gpus = 0
        self.__devices = []
        self.__GPUMetrics = {}
        self.__metricMapping = {}
        self.__ecc_ras_monitoring = runtimeConfig["collector_ras_ecc"]
        self.__power_cap_monitoring = runtimeConfig["collector_power_capping"]
        self.__eccBlocks = {}
        # verify minimum version met
        check_min_version("24.7.1")

    def get_gpu_metrics(self, device):
        """Make GPU metric query and return dict of tracked metrics"""

        tracked_metrics = {}
        result = smi.amdsmi_get_gpu_metrics_info(device)
        for smiName, metricName in self.__metricMapping.items():
            tracked_metrics[metricName] = result[smiName]
        return tracked_metrics

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

        # determine GPU index mapping (ie. map kfd indices used by SMI lib to that of HIP_VISIBLE_DEVICES)
        guidMapping = {}
        for index, device in enumerate(self.__devices):
            kfd_info = smi.amdsmi_get_gpu_kfd_info(device)
            guidMapping[index] = kfd_info["kfd_id"]
        self.__indexMapping = gpu_index_mapping_based_on_guids(guidMapping, self.__num_gpus)

        # version info metric
        version_metric = Gauge(
            self.__prefix + "version_info",
            "GPU versioning information",
            labelnames=["card", "driver_ver", "vbios", "type", "schema"],
        )

        for idx, device in enumerate(self.__devices):
            gpuLabel = self.__indexMapping[idx]
            vbios_info = smi.amdsmi_get_gpu_vbios_info(device)
            vbios = vbios_info["part_number"]
            asic_info = smi.amdsmi_get_gpu_asic_info(device)
            devtype = asic_info["market_name"]

            driver_info = smi.amdsmi_get_gpu_driver_info(device)
            gpuDriverVer = driver_info["driver_version"]

            version_metric.labels(
                card=gpuLabel, driver_ver=gpuDriverVer, vbios=vbios, type=devtype, schema=self.__schema
            ).set(1)

        # Register memory related metrics
        self.__GPUMetrics["vram_total_bytes"] = Gauge(
            self.__prefix + "vram_total_bytes", "VRAM Memory in Use (%)", labelnames=["card"]
        )
        self.__GPUMetrics["vram_used_percentage"] = Gauge(
            self.__prefix + "vram_used_percentage", "VRAM Memory in Use (%)", labelnames=["card"]
        )

        # Register RAS ECC related metrics
        if self.__ecc_ras_monitoring:
            for block in smi.AmdSmiGpuBlock:
                if block == smi.AmdSmiGpuBlock.INVALID:
                    continue
                logging.debug("Checking on %s ECC status.." % block)
                status = smi.amdsmi_get_gpu_ecc_status(self.__devices[0], block)
                if status == smi.AmdSmiRasErrState.ENABLED:
                    # check if queryable
                    try:
                        status = smi.amdsmi_get_gpu_ecc_count(self.__devices[0], block)
                        key = "%s" % block
                        key = key.removeprefix("AmdSmiGpuBlock.").lower()
                        self.__eccBlocks[key] = block
                        metric = "ras_%s_correctable_count" % key
                        self.__GPUMetrics[metric] = Gauge(
                            self.__prefix + metric,
                            "number of correctable RAS events for %s block (count)" % key,
                            labelnames=["card"],
                        )
                        metric = "ras_%s_uncorrectable_count" % key
                        self.__GPUMetrics[metric] = Gauge(
                            self.__prefix + metric,
                            "number of uncorrectable RAS events for %s block (count)" % key,
                            labelnames=["card"],
                        )
                        metric = "ras_%s_deferred_count" % key
                        self.__GPUMetrics[metric] = Gauge(
                            self.__prefix + metric,
                            "number of deferred RAS events for %s block (count)" % key,
                            labelnames=["card"],
                        )
                    except:
                        logging.debug("Skipping RAS definition for %s" % block)

        # Cache valid primary temperature location and register with location label
        dev0 = self.__devices[0]
        for item in smi.AmdSmiTemperatureType:
            try:
                temperature = smi.amdsmi_get_temp_metric(dev0, item, smi.AmdSmiTemperatureMetric.CURRENT)
            except smi.AmdSmiException:
                continue
            if temperature > 0:
                self.__temp_location_index = item
                self.__temp_location_name = item.name.lower()
                logging.info("--> Using primary temperature location at %s" % self.__temp_location_name)
                break
        self.__GPUMetrics["temperature_celsius"] = Gauge(
            self.__prefix + "temperature_celsius", "Temperature (C)", labelnames=["card", "location"]
        )

        # Cache valid memory temperature location and register with location label
        self.__temp_memory_location_index = None
        dev0 = self.__devices[0]
        for item in smi.AmdSmiTemperatureType:
            if "HBM" in item.name or "VRAM" in item.name:
                try:
                    temperature = smi.amdsmi_get_temp_metric(dev0, item, smi.AmdSmiTemperatureMetric.CURRENT)
                except smi.AmdSmiException:
                    continue
                if temperature > 0:
                    self.__temp_memory_location_index = item
                    self.__temp_memory_location_name = item.name.lower()
                    logging.info("--> Using HBM temperature location at %s" % self.__temp_memory_location_name)
                    break
            else:
                continue

        if self.__temp_memory_location_index:
            self.__GPUMetrics["temperature_memory_celsius"] = Gauge(
                self.__prefix + "temperature_memory_celsius", "HBM Temperature (C)", labelnames=["card", "location"]
            )

        # Define mapping from amdsmi variable names to omnistat metric, incuding units where appropriate
        self.__metricMapping = {
            # core GPU metric definitions
            "average_gfx_activity": "utilization_percentage",
            "average_uclk_frequency": "mclk_clock_mhz",
            "average_umc_activity": "vram_busy_percentage",
        }

        # additional mappings: depending on architecture, amdsmi reports clock frequencies and socket power
        # via different keys - check here to determine metric availability and log the source as a label
        metric_check = {}
        metric_check["sclk_clock_mhz"] = ["average_gfxclk_frequency", "current_gfxclk"]
        metric_check["average_socket_power_watts"] = ["average_socket_power", "current_socket_power"]
        metric_check["mclk_clock_mhz"] = ["average_uclk_frequency", "current_uclk"]

        dev0 = self.__devices[0]
        metrics = smi.amdsmi_get_gpu_metrics_info(dev0)
        self.__source_labels = {}

        for desired_metric in metric_check:
            found = None
            for key in metric_check[desired_metric]:
                if is_positive_int(metrics[key]):
                    self.__metricMapping[key] = desired_metric
                    self.__source_labels[desired_metric] = key
                    found = key
                    break
            if not found:
                logging.error("--> Unable to determine valid data for %s" % desired_metric)
                logging.error("")
                sys.exit(4)
            else:
                logging.info("--> Using mapping %s -> %s " % (desired_metric, found))
                self.__GPUMetrics[self.__prefix + desired_metric] = Gauge(
                    self.__prefix + desired_metric, f"{desired_metric}", labelnames=["card", "source"]
                )

        # Register remaining metrics of interest available from get_gpu_metrics()
        for idx, device in enumerate(self.__devices):
            metrics = self.get_gpu_metrics(device)
            for metric in metrics:
                metric_name = self.__prefix + metric
                # add Gauge metric only once
                if metric_name not in self.__GPUMetrics.keys():
                    self.__GPUMetrics[metric_name] = Gauge(metric_name, f"{metric}", labelnames=["card"])

        # Register power capping setting
        if self.__power_cap_monitoring:
            self.__GPUMetrics["power_cap_watts"] = Gauge(
                self.__prefix + "power_cap_watts", "Max power cap of device (W)", labelnames=["card"]
            )

        return

    def updateMetrics(self):
        self.collect_data_incremental()
        return

    def collect_data_incremental(self):
        for idx, device in enumerate(self.__devices):

            # map GPU index
            cardId = self.__indexMapping[idx]

            #  stats available via get_gpu_metrics
            metrics = self.get_gpu_metrics(device)

            for metricName, value in metrics.items():
                metric = self.__GPUMetrics[self.__prefix + metricName]
                if metricName in self.__source_labels:
                    metric.labels(card=cardId, source=self.__source_labels[metricName]).set(value)
                else:
                    metric.labels(card=cardId).set(value)

            # additional gpu memory-related stats
            device_total_vram = smi.amdsmi_get_gpu_memory_total(device, smi.AmdSmiMemoryType.VRAM)
            self.__GPUMetrics["vram_total_bytes"].labels(card=cardId).set(device_total_vram)
            vram_used_bytes = smi.amdsmi_get_gpu_memory_usage(device, smi.AmdSmiMemoryType.VRAM)
            percentage = round(100.0 * vram_used_bytes / device_total_vram, 4)
            self.__GPUMetrics["vram_used_percentage"].labels(card=cardId).set(percentage)

            # additional temperature-related stats
            temperature = smi.amdsmi_get_temp_metric(
                device, self.__temp_location_index, smi.AmdSmiTemperatureMetric.CURRENT
            )
            self.__GPUMetrics["temperature_celsius"].labels(card=cardId, location=self.__temp_location_name).set(
                temperature
            )
            if self.__temp_memory_location_index:
                hbm_temperature = smi.amdsmi_get_temp_metric(
                    device, self.__temp_memory_location_index, smi.AmdSmiTemperatureMetric.CURRENT
                )
                self.__GPUMetrics["temperature_memory_celsius"].labels(
                    card=cardId, location=self.__temp_memory_location_name
                ).set(hbm_temperature)

            # RAS counts
            if self.__ecc_ras_monitoring:
                for key, block in self.__eccBlocks.items():
                    ecc_error_counts = smi.amdsmi_get_gpu_ecc_count(device, block)
                    metric = "ras_%s_correctable_count" % key
                    self.__GPUMetrics["ras_%s_correctable_count" % key].labels(card=cardId).set(
                        ecc_error_counts["correctable_count"]
                    )
                    self.__GPUMetrics["ras_%s_uncorrectable_count" % key].labels(card=cardId).set(
                        ecc_error_counts["uncorrectable_count"]
                    )
                    self.__GPUMetrics["ras_%s_deferred_count" % key].labels(card=cardId).set(
                        ecc_error_counts["deferred_count"]
                    )
            # power-capping
            if self.__power_cap_monitoring:
                power_info = smi.amdsmi_get_power_cap_info(device)
                self.__GPUMetrics["power_cap_watts"].labels(card=cardId).set(power_info["power_cap"] / 1000000)

        return
