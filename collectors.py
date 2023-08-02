# Prometheus data collector for HPC systems.
#
# Parent collector class - defines required methods for all metric collectors implemented as a child class. 
#--

import logging
import sys
from collector_base import Collector
from prometheus_client import CollectorRegistry

class ROCM(Collector):
    def __init__(self):
        logging.debug("Initializing ROCm data collector")
        
        # command-line flags for use with rocm-smi to obtained desired metrics
        self.__rocm_smi_flags = "-P -u -f -t --showmeminfo vram --json"

        # list of desired metrics to query: (prometheus_metric_name -> rocm-smi-key)
        self.__rocm_smi_metrics = {
            "temp_die_edge": "Temperature (Sensor edge) (C)",
            "avg_pwr": "Average Graphics Package Power (W)",
            "utilization": "GPU use (%)",
            "vram_total": "VRAM Total Memory (B)",
            "vram_used": "VRAM Total Used Memory (B)",
        }
        logging.debug("rocm_smi_flags = %s" % self.__rocm_smi_flags)

    #--------------------------------------------------------------------------------------
    # Required child methods

    # Required method to implemented by child classes
    def registerMetrics(self):
        logging.error("[ERROR]: data collectors must implement registerMetrics() method.")
        sys.exit(1)
        return

    # Required method to implemented by child classes
    def updateMetrics(self):
        logging.error("[ERROR]: data collectors must implement updateMetrics() method.")
        sys.exit(1)
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
