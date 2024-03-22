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
        self.__metrics = []
        self.__session = DeviceSession()
        self.__session.create(self.__names)
        logging.info("pyrocprofiler initialized")

    def registerMetrics(self):
        prefix = "card0_rocprofiler_"
        for name in self.__names:
            metric_name = prefix + name
            self.__metrics.append(Gauge(metric_name, ""))
            logging.info("  --> [registered] %s (gauge)" % (metric_name))
        self.__session.start()

    def updateMetrics(self):
        values = self.__session.poll()
        for i, _ in enumerate(self.__metrics):
            self.__metrics[i].set(values[i])
        return generate_latest()
