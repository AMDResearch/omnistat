import logging
import os
import sys

from prometheus_client import Gauge, generate_latest
from pyrocprofiler import DeviceSession

from collector_base import Collector

class rocprofiler(Collector):
    def __init__(self, names):
        logging.debug("Initializing rocprofiler data collector")
        self.__names = names
        self.__session = DeviceSession()
        num_gpus = self.__session.create(self.__names)
        self.__metrics = [[]] * num_gpus
        logging.info("pyrocprofiler initialized")

    def registerMetrics(self):
        for gpu_id, gpu_metrics in enumerate(self.__metrics):
            prefix = f"card{gpu_id}_rocprofiler_"
            for name in self.__names:
                metric_name = prefix + name
                gpu_metrics.append(Gauge(metric_name, ""))
                logging.info("  --> [registered] %s (gauge)" % (metric_name))
        self.__session.start()

    def updateMetrics(self):
        values = self.__session.poll()
        for i, _ in enumerate(self.__metrics):
            for j, _ in enumerate(self.__names):
                self.__metrics[i][j].set(values[i][j])
        return generate_latest()
