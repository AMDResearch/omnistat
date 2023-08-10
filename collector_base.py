# Prometheus data collector for HPC systems.
#
# Base Collector class - defines required methods for all metric collectors 
# implemented as a child class.
#--

from abc import ABC, abstractmethod

class Collector(ABC):
    # Required methods to be implemented by child classes
    @abstractmethod
    def registerMetrics(self):
        """Defines desired metrics to monitor with Prometheus. Called once during initialization.
        """
        pass

    @abstractmethod
    def updateMetrics(self):
        """Updates defined metrics with latest values. Called at every polling interval.
        """
        pass
