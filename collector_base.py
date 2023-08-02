# Prometheus data collector for HPC systems.
#
# Base collector class - defines required methods for all metric collectors implemented as a child class.
#--

import logging
import sys
from abc import ABC, abstractmethod

class Collector(ABC):
    # Required methods to be implemented by child classes
    @abstractmethod
    def registerMetrics(self):
        pass
    @abstractmethod
    def updateMetrics(self):
        pass

# class Metrics(ABC):
#     def __init__(self):
#         logging.basicConfig(
#             format="%(message)s", level=logging.DEBUG, stream=sys.stdout
#         )
#         # defined GPU prometheus metrics (stored on a per-gpu basis)
#         self.__GPUmetrics = {}
 
#         # defined global prometheus metrics
#         self.__globalMetrics = {}
#         self.__registry_global = CollectorRegistry()
#         # Resource manager type
#         self.__rms = "slurm"

#         # define desired collectors
#         self.__collectors = []

#         rocmSMI = True
#         if rocmSMI:
#             from collectors import ROCM
#             self.__collectors.append(ROCM())

#         logging.debug("Completed collector initialization (base class)")
#         return

    # # Required method to implemented by child classes
    # def registerMetrics(self):
    #     logging.error("[ERROR]: data collectors must implement registerMetrics() method.")
    #     sys.exit(1)
    #     return

    # # Required method to implemented by child classes
    # @abstractmethod
    # def registerMetrics(self):
    #     pass

    # # Required method to implemented by child classes
    # def updateMetrics(self):
    #     logging.error("[ERROR]: data collectors must implement updateMetrics() method.")
    #     sys.exit(1)
    #     return
