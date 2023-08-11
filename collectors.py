# Prometheus data collector for HPC systems.
#
# Custom collector(s) - defines required methods for all metric collectors 
# implemented as a child class. 
#--

import sys
import utils
import json
import logging
import os
import shutil
from collector_base import Collector
from prometheus_client import Gauge, generate_latest, CollectorRegistry

class ROCMSMI(Collector):
    def __init__(self):
        logging.debug("Initializing ROCm SMI data collector")
        self.__prefix = "rocm_"
        
        # allow for env variable to prescribe path to rocm-smi
        rocm_smi_command = "rocm-smi"
        if "ROCM_SMI_PATH" in os.environ:
            rocmPath = os.getenv("ROCM_SMI_PATH")
            logging.debug("Overriding path with ROCM_SMI_PATH=%s" % rocmPath)
            if os.path.isdir(rocmPath):
                rocm_smi_command = rocmPath + "/rocm-smi"
            else:
                utils.error("provided ROCM_SMI_PATH does not exist -> %s" % rocmPath)
                sys.exit(1)
        
        # verify we can resolve the rocm-smi binary
        path = shutil.which(rocm_smi_command)
        if not path:
            utils.error("Unable to resolve path for rocm-smi -> %s" % rocm_smi_command)
        else:
            logging.debug("rocm-smi path = %s" % path)

        # command-line flags for use with rocm-smi to obtained desired metrics
        rocm_smi_flags = "-P -u -f -t --showmeminfo vram --json"
        # cache query command with options
        self.__rocm_smi_query = [rocm_smi_command] + rocm_smi_flags.split()
 
        # list of desired metrics to query: (prometheus_metric_name -> rocm-smi-key)
        self.__rocm_smi_metrics = {
            self.__prefix+"temp_die_edge": "Temperature (Sensor edge) (C)",
            self.__prefix+"avg_pwr": "Average Graphics Package Power (W)",
            self.__prefix+"utilization": "GPU use (%)",
            self.__prefix+"vram_total": "VRAM Total Memory (B)",
            self.__prefix+"vram_used": "VRAM Total Used Memory (B)",
        }

        logging.debug("rocm_smi_exec = %s" % self.__rocm_smi_query)

        self.__GPUmetrics = {}

    #--------------------------------------------------------------------------------------
    # Required child methods

    def registerMetrics(self):
        """Run rocm-smi and register metrics of interest"""

        data = utils.runShellCommand(self.__rocm_smi_query, exit_on_error=True)
        data = json.loads(data.stdout)

        # register number of GPUs
        numGPUs_metric = Gauge(self.__prefix + "num_gpus","# of GPUS available on host")
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
                    self.__GPUmetrics[gpu][metric].set(value)
                    logging.debug("updated: %s = %s" % (metric, value))
        return
