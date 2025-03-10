import ctypes
import logging
import os
import sys

from prometheus_client import Gauge, generate_latest

from omnistat.collector_base import Collector


class rocprofiler_counter_value_t(ctypes.Structure):
    _fields_ = [
        ("value", ctypes.c_uint64),
    ]


class rocprofiler_device_profile_metric_t(ctypes.Structure):
    _fields_ = [
        ("metric_name", ctypes.c_char * 64),
        ("value", rocprofiler_counter_value_t),
    ]


class rocprofiler_session_id_t(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint64),
    ]


class rocprofiler(Collector):
    def __init__(self, rocm_path, metric_names):
        logging.debug("Initializing rocprofiler data collector")

        hip_lib = rocm_path + "/lib/libamdhip64.so"
        rocprofiler_lib = rocm_path + "/lib/librocprofiler64v2.so"

        if not os.path.isfile(hip_lib):
            logging.error("ERROR: Unable to load HIP library.")
            logging.error("--> looking for %s" % hip_lib)
            sys.exit(4)

        if not os.path.isfile(rocprofiler_lib):
            logging.error("ERROR: Unable to load rocprofiler library.")
            logging.error("--> looking for %s" % rocprofiler_lib)
            sys.exit(4)

        self.__libhip = ctypes.CDLL(hip_lib)
        self.__librocprofiler = ctypes.CDLL(rocprofiler_lib)

        logging.info("Runtime library loaded from %s" % hip_lib)
        logging.info("Runtime library loaded from %s" % rocprofiler_lib)

        num_gpus = (ctypes.c_int)()
        status = self.__libhip.hipGetDeviceCount(ctypes.byref(num_gpus))
        assert status == 0
        status = self.__librocprofiler.rocprofiler_initialize()
        assert status == 0
        logging.info("rocprofiler library API initialized")

        self.__num_gpus = num_gpus.value
        self.__names = metric_names

        # List of Prometheus gauges, one for each metric
        self.__metrics = []

        # Lists indexed by GPU ID:
        #  __sessions: stores rocprofiler device mode sessions
        #  __values: stores arrays of values returned by rocprofiler
        self.__sessions = []
        self.__values = []

        for i in range(self.__num_gpus):
            self.__sessions.append((rocprofiler_session_id_t)())
            self.__values.append((rocprofiler_device_profile_metric_t * len(self.__names))())

        logging.info(f"--> rocprofiler: number of GPUs detected = {self.__num_gpus}")
        logging.info(f"--> rocprofiler: metrics = {self.__names}")

        # Convert list of metrics to pass with ctypes
        names_bytes = [bytes(i, "utf-8") for i in self.__names]
        names_array = (ctypes.c_char_p * len(names_bytes))()
        names_array[:] = names_bytes

        # Create rocprofiler sessions for each GPU
        for i in range(self.__num_gpus):
            self.__librocprofiler.rocprofiler_device_profiling_session_create(
                names_array, len(names_array), ctypes.byref(self.__sessions[i]), 0, i
            )

        logging.info("--> rocprofiler initialized")

    def registerMetrics(self):
        prefix = f"rocprofiler_"
        for metric in self.__names:
            metric_name = prefix + metric
            self.__metrics.append(Gauge(metric_name, "", labelnames=["card"]))
            logging.info("--> [registered] %s (gauge)" % (metric_name))

        for i in range(self.__num_gpus):
            self.__librocprofiler.rocprofiler_device_profiling_session_start(self.__sessions[i])

    def updateMetrics(self):
        for i in range(self.__num_gpus):
            self.__librocprofiler.rocprofiler_device_profiling_session_poll(self.__sessions[i], self.__values[i])

            # Reset sessions to address issues with values (SWDEV-468600)
            self.__librocprofiler.rocprofiler_device_profiling_session_stop(self.__sessions[i])
            self.__librocprofiler.rocprofiler_device_profiling_session_start(self.__sessions[i])

        for i in range(self.__num_gpus):
            for j in range(len(self.__names)):
                array = self.__values[i]
                value = array[j].value.value
                self.__metrics[j].labels(card=i).set(value)

        return
