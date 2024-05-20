import logging
import os
import sys

from prometheus_client import Gauge, generate_latest
from pyrocprofiler import DeviceSession

from collector_base import Collector

class rocprofiler2(Collector):
    def __init__(self, names):
        logging.debug("Initializing rocprofiler data collector")
        self.__names = names
        self.__initialized = False
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
                metric_name = 'koomie_' + prefix + metric
                self.__GPUmetrics[gpu].append(Gauge(metric_name, ""))
                logging.info("  --> [registered] %s (gauge)" % (metric_name))
        self.__session.start()

    # def updateMetrics_orig(self):
    #     values = self.__session.poll()
    #     for gpu in range(self.__num_gpus):
    #         for j, _ in enumerate(values[gpu]):
    #             self.__GPUmetrics[gpu][j].set(values[gpu][j])
    #     return generate_latest()

    def updateMetrics(self):
        # if self.__initialized:
        #     old = values
        values = self.__session.poll()
        if self.__initialized == True:
            for gpu in range(self.__num_gpus):
                for j, _ in enumerate(values[gpu]):
                    self.__GPUmetrics[gpu][j].set(values[gpu][j] - self.__prev_values[gpu][j])
        
        self.__prev_values = values
#        self.__session.fake_event()
        self.__session.stop()
        self.__session.start()
        self.__initialized = True
        return generate_latest()    
