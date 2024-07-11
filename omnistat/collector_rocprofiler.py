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
        logging.info("--> pyrocprofiler: number of GPUs detected = %i" % self.__num_gpus)
        self.__metrics = []
        logging.info("--> pyrocprofiler initialized")

    def registerMetrics(self):
        prefix = f"rocm_rocprofiler_"
        for metric in self.__names:
            metric_name = prefix + metric
            self.__metrics.append(Gauge(metric_name, "", labelnames=["card"]))
            logging.info("  --> [registered] %s (gauge)" % (metric_name))
        self.__session.start()

    def updateMetrics(self):
        values = self.__session.poll()
        for gpu in range(self.__num_gpus):
            for i, _ in enumerate(values[gpu]):
                self.__metrics[i].labels(card=gpu).set(values[gpu][i])
        # Reset session to address issues with values (SWDEV-468600)
        self.__session.stop()
        self.__session.start()
        return generate_latest()
