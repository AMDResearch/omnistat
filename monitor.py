# Prometheus data collector for HPC systems.
#
# Supporting monitor class to implement a prometheus data collector with one more custom collector.
#--

import logging
import sys
from prometheus_client import CollectorRegistry

class Monitor():
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

        # define desired collectors
        self.__collectors = []

        rocmSMI = True
        if rocmSMI:
            from collectors import ROCM
            self.__collectors.append(ROCM())

        logging.debug("Completed collector initialization (base class)")
        return