# Prometheus data collector for HPC systems.
#
# Parent collector class - defines required methods for all metric collectors implemented as a child class. 
#--

import sys
import utils
import json
import logging
from collector_base import Collector
from prometheus_client import Gauge, generate_latest, CollectorRegistry

class ROCMSMI(Collector):
    def __init__(self):
        logging.debug("Initializing ROCm data collector")
        prefix = "rocm_"
        
        # command-line flags for use with rocm-smi to obtained desired metrics
        self.__rocm_smi_flags = "-P -u -f -t --showmeminfo vram --json"

        # list of desired metrics to query: (prometheus_metric_name -> rocm-smi-key)
        self.__rocm_smi_metrics = {
            prefix+"temp_die_edge": "Temperature (Sensor edge) (C)",
            prefix+"avg_pwr": "Average Graphics Package Power (W)",
            prefix+"utilization": "GPU use (%)",
            prefix+"vram_total": "VRAM Total Memory (B)",
            prefix+"vram_used": "VRAM Total Used Memory (B)",
        }
        logging.debug("rocm_smi_flags = %s" % self.__rocm_smi_flags)

        self.__GPUmetrics = {}

    #--------------------------------------------------------------------------------------
    # Required child methods

    def registerMetrics(self):
        """Run rocm-smi and register metrics of interest"""

        command = ["rocm-smi"] + self.__rocm_smi_flags.split()
        data = utils.runShellCommand(command, exit_on_error=True)
        data = json.loads(data.stdout)
        for gpu in data:
            logging.debug("%s: gpu detected" % gpu)
            # init storage per gpu
            self.__GPUmetrics[gpu] = {}

            # look for matching metrics and register
            for metric in self.__rocm_smi_metrics:
                rocmName = self.__rocm_smi_metrics[metric]
                # if metric[1] in data[gpu]:
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

    #--------------------------------------------------------------------------------------
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
        command = ["rocm-smi"] + self.__rocm_smi_flags.split()
        data = utils.runShellCommand(command)
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
                    self.__GPUmetrics[gpu][metric].set(value)
                    logging.debug("updated: %s = %s" % (metric, value))
        return
