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
        self.__num_gpus = self.__session.create(self.__names)
        logging.info(
            "--> pyrocprofiler: number of GPUs detected = %i" % self.__num_gpus
        )
        self.__GPUmetrics = [None] * self.__num_gpus
        logging.info("--> pyrocprofiler initialized")

    def registerMetrics(self):
        for gpu in range(self.__num_gpus):
            self.__GPUmetrics[gpu] = []
            prefix = f"card{gpu}_rocprofiler_"
            for metric in self.__names:
                metric_name = prefix + metric
                self.__GPUmetrics[gpu].append(Gauge(metric_name, ""))
                logging.info("  --> [registered] %s (gauge)" % (metric_name))
        self.__session.start()

    def updateMetrics(self):
        values = self.__session.poll()
        for gpu in range(self.__num_gpus):
            for j, _ in enumerate(values[gpu]):
                self.__GPUmetrics[gpu][j].set(values[gpu][j])
        return generate_latest()
