# Prometheus data collector for HPC systems.
#
# Supporting monitor class to implement a prometheus data collector with one 
# more custom collector(s).
#--

import logging
import sys
import re
import platform
from prometheus_client import generate_latest, CollectorRegistry

class Monitor():
    def __init__(self):
        logging.basicConfig(
            format="%(message)s", level=logging.INFO, stream=sys.stdout
        )
        # defined GPU prometheus metrics (stored on a per-gpu basis)
        # self.__GPUmetrics = {}
 
        # defined global prometheus metrics
        self.__globalMetrics = {}
        self.__registry_global = CollectorRegistry()
        # Resource manager type
        self.__rms = "slurm"

        # define desired collectors
        self.__collectors = []

        self.enableROCmCollector = True
        self.enableSLURMCollector = True

        # allow for disablement of slurm collector via regex match
        SLURM_host_skip="login.*"
        hostname = platform.node().split('.', 1)[0]
        p = re.compile(SLURM_host_skip)
        if p.match(hostname):
            self.enableSLURMCollector = False

        logging.debug("Completed collector initialization (base class)")
        return

    def initMetrics(self):
        rocmSMI = True
        enableSLURM = True

        if self.enableROCmCollector:
            from collectors import ROCMSMI
            self.__collectors.append(ROCMSMI())
        if self.enableSLURMCollector:
            from collectors import SlurmJob
            self.__collectors.append(SlurmJob())
        
        # Initialize all metrics
        for collector in self.__collectors:
            collector.registerMetrics()

        # Gather metrics on startup
        for collector in self.__collectors:
            collector.updateMetrics()

    def updateAllMetrics(self):
        for collector in self.__collectors:
            collector.updateMetrics()
        return generate_latest()