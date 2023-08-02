# Prometheus data collector for HPC systems.
#
# Parent collector class - defines required methods for all metric collectors implemented as a child class. 
#--

import logging
import sys
from prometheus_client import CollectorRegistry

class Collector:
    def __init__(self):
        logging.basicConfig(
            format="%(message)s", level=logging.DEBUG, stream=sys.stdout
        )
        # defined GPU prometheus metrics (stored on a per-gpu basis)
        self.__GPUmetrics = {}
 
        # defined global prometheus metrics
        self.__globalMetrics = {}
        self.__registry_global = CollectorRegistry()
        # Resource manager type
        self.__rms = "slurm"

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
