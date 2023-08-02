# Prometheus data collector for HPC systems.
#
# Base Collector class - defines required methods for all metric collectors implemented as a child class.
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
