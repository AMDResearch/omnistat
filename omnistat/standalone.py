#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2023 - 2024 Advanced Micro Devices, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -------------------------------------------------------------------------------
#
# Standalone data collector for HPC systems.
# --> intended for user-mode data collection to run within a job

import argparse
import ctypes
import getpass
import logging
import os
import pandas as pd
import platform
import sqlite3
import sys
import tables
import time
import warnings
from prometheus_client import Gauge, REGISTRY

# Ensure current directory is part of Python's path; allows direct execution
# from the top directory of the project when package is not installed.
if os.path.isdir("omnistat") and sys.path[0]:
    sys.path.insert(0, "")

from omnistat import utils
from omnistat.monitor import Monitor


class Standalone:
    def __init__(self):
        logging.basicConfig(format="%(message)s", level=logging.ERROR, stream=sys.stdout)
        self.__data = {}

        # Create a die file - process terminates cleanly if this file is removed
        user = getpass.getuser()
        self.__dieFile = "/tmp/.omnistat_standalone_%s" % user
        try:
            with open(self.__dieFile, "w") as file:
                file.write("Remove this file to terminate standalone data collection")
        except:
            logging.error("Unable to create die file -> %s" % self.__dieFile)

        logging.info("Die file created (%s)" % self.__dieFile)

        # Init glibc for usleep access
        self.__libc = ctypes.CDLL("libc.so.6")

    def sleep_microsecs(self, microsecs):
        self.__libc.usleep(microsecs)

    def tokenizeMetricName(self, name, labels):
        token = name
        if "card" in labels:
            token = "card%s_" % labels["card"] + name
        return token

    def initMetrics(self, prefix=None):
        """Initialize data structure to house caching of telemetry data"""
        for metric in REGISTRY.collect():
            if metric.type == "gauge":
                if prefix and not metric.name.startswith(prefix):
                    continue
                for sample in metric.samples:
                    token = self.tokenizeMetricName(sample.name, sample.labels)
                    logging.debug("Enabling caching for metric -> %s" % token)
                    self.__data[token] = []

    def getMetrics(self, timestamp, prefix=None):
        """Cache current metrics from latest Prometheus query"""
        for metric in REGISTRY.collect():
            if metric.type == "gauge":
                if prefix and not metric.name.startswith(prefix):
                    continue
                for sample in metric.samples:
                    token = self.tokenizeMetricName(sample.name, sample.labels)
                    self.__data[token].append([timestamp, sample.value])

    def checkForTermination(self):
        if os.path.exists(self.__dieFile):
            return False
        else:
            return True

    def dumpCache(self, mode="raw", filename="/tmp/omnistat_data"):

        hostname = platform.node().split(".", 1)[0]

        if mode == "raw":
            print(self.__data)
        elif mode == "pandas-sqlite":
            filename += ".db"
            logging.info("Save local node telemetry in pandas/sqlite format -> %s" % filename)
            # no hyphens for sql
            hostname = hostname.replace("-","_")
            output = {}
            if os.path.exists(filename):
                os.remove(filename)

            # Save to sql DB
            with sqlite3.connect(filename) as conn:
                for metric in self.__data:
                    data = self.__data[metric]
                    df = pd.DataFrame(data, columns=["Timestamp", "Value"])

                    if metric.startswith("card"):
                        card, delim, name = metric.partition("_")
                        table_name = "%s__%s__%s" % (hostname, card, name)
                    else:
                        table_name = "%s__%s" % (hostname, metric)
                    df.to_sql(table_name, conn, if_exists="append", index=False)

        elif mode == "pandas-hdf5":
            filename += ".h5"
            warnings.filterwarnings("ignore", category=tables.exceptions.NaturalNameWarning)
            output = {}

            if os.path.exists(filename):
                os.remove(filename)
            for metric in self.__data:
                data = self.__data[metric]
                df = pd.DataFrame(data, columns=["Timestamp", "Value"])
                if metric.startswith("card"):
                    card, delim, name = metric.partition("_")
                    hdfPath = "%s/%s/%s" % (hostname, card, name)
                else:
                    hdfPath = "%s/%s" % (hostname, metric)
                df.to_hdf(filename, key=hdfPath, mode="a", format="fixed")
        else:
            logging.error("Unsupported dumpCache mode -> %s" % mode)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", type=str, help="runtime config file", default=None)
    parser.add_argument("--interval", type=float, help="sampling frequencey (in secs)", default=0.5)
    args = parser.parse_args()

    interval_secs = args.interval
    assert interval_secs > 0.005

    config = utils.readConfig(utils.findConfigFile(args.configfile))

    # Initialize GPU monitoring
    monitor = Monitor(config)
    monitor.initMetrics()
    # Initialize standalone polling
    caching = Standalone()
    caching.initMetrics(prefix="rocm")

    interval_microsecs = int(interval_secs * 1000000)
    exit_check_interval_secs = 5.0

    # ---
    # Main polling loop
    num_samples = 0
    sample_duration = 0
    exit_check_duration = 0
    mem_mb_base = utils.getMemoryUsageMB()

    try:
        while True:
            start_time = time.perf_counter()
            timestamp = pd.Timestamp("now")
            monitor.updateAllMetrics()
            caching.getMetrics(timestamp, prefix="rocm")
            sample_duration += time.perf_counter() - start_time

            num_samples += 1

            if exit_check_duration > exit_check_interval_secs:
                logging.debug("Check if received request to terminate")
                exit_check_duration = 0.0
                if caching.checkForTermination():
                    logging.info("Terminating per request...")

                    break

            caching.sleep_microsecs(interval_microsecs)
            exit_check_duration += time.perf_counter() - start_time
    except KeyboardInterrupt:
        logging.info("\nTerminating data collection from keyboard interrupt.")

    # end polling loop
    # ---

    logging.info("--> Sampling interval          = %f (secs)" % interval_secs)
    logging.info("--> Total # of samples         = %i" % num_samples)
    logging.info("--> Average time/sample        = %.5f (secs)" % (sample_duration / num_samples))

    mem_mb = utils.getMemoryUsageMB()
    logging.info("--> Base memory in use         = %.3f MB" % mem_mb_base)
    logging.info("--> Memory growth from caching = %.3f MB" % (mem_mb - mem_mb_base))

    duration_secs = num_samples * interval_secs
    mem_per_hour = 3600.0 * ((mem_mb - mem_mb_base) / duration_secs)
    logging.info("--> Data collection duration   = %.2f (secs)" % duration_secs)
    logging.info("--> Approx. mem growth/hour    = %.3f (MB)" % mem_per_hour)

    hostname = platform.node().split(".", 1)[0]
    caching.dumpCache(mode="pandas-sqlite", filename="/tmp/omnistat.%s" % hostname)


if __name__ == "__main__":
    main()
