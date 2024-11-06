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
# --> provides a flask endpoint to terminate data collection (http://host:port/shutdown)

import argparse
import ctypes
import getpass
import logging
import os
import platform
import requests
import sys
import signal
import threading
import time
import warnings
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from prometheus_client import Gauge, REGISTRY

# Ensure current directory is part of Python's path; allows direct execution
# from the top directory of the project when package is not installed.
if os.path.isdir("omnistat") and sys.path[0]:
    sys.path.insert(0, "")

from omnistat import utils
from omnistat.monitor import Monitor


app = Flask(__name__)
terminateFlagEvent = threading.Event()
dataDeliveredEvent = threading.Event()


def push_to_victoria_metrics(metrics_data_list, victoria_url):
    headers = {
        "Content-Type": "text/plain",
    }

    metrics_data = "\n".join(metrics_data_list)
    response = requests.post(victoria_url, data=metrics_data, headers=headers)

    if response.status_code != 204:
        logging.error(f"Failed to push metrics: {response.status_code}, {response.text}")
        sys.exit(1)
    else:
        logging.info("Metrics pushed successfully!")


class Standalone:
    def __init__(self, args, config):
        logging.basicConfig(format="%(message)s", level=logging.ERROR, stream=sys.stdout, flush=True)
        self.__data = {}
        self.__dataVM = []
        self.__hostname = platform.node().split(".", 1)[0]
        self.__victoriaURL = f"http://{args.endpoint}:{args.port}/api/v1/import/prometheus"
        self.__pushFrequencyMins = config["omnistat.usermode"].getint("push_frequency_mins", 5)
        if self.__pushFrequencyMins < 1:
            logging.error("")
            logging.error("[ERROR]: Please set data_frequency_mins >= 1 minute (%s)" % self.__pushFrequencyMins)
            sys.exit(1)

        logging.info("Cached data will be pushed every %i minute(s)" % self.__pushFrequencyMins)

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
                    # account for possibility of dynamic metric definitions (e.g. annotations)
                    if token not in self.__data:
                        self.__data[token] = []
                        logging.debug("Enabling caching for metric -> %s" % token)
                    labels = 'instance="%s"' % self.__hostname
                    if sample.labels:
                        for key, value in sample.labels.items():
                            labels += ',%s="%s"' % (key, value)
                    entry = "%s{%s} %s %i" % (sample.name, labels, sample.value, int(timestamp.timestamp() * 1000))
                    self.__dataVM.append(entry)
                    if token == "rmsjob_annotations":
                        print("%s: %s" % (timestamp, sample.value))

    def dumpCache(self, mode="victoria"):

        if mode == "victoria":
            if len(self.__dataVM) == 0:
                return
            logging.info("")
            logging.info("Pushing local node telemetry to VictoriaMetrics endpoint -> %s" % self.__victoriaURL)
            try:
                push_to_victoria_metrics(self.__dataVM, self.__victoriaURL)
            except:
                logging.error("")
                logging.error("ERROR: Unable to push cached metrics -> please verify local server is running.")
                logging.error("ERROR: Collected data not saved :-(")
                logging.error("")
                sys.exit(4)
        else:
            logging.error("Unsupported dumpCache mode -> %s" % mode)
            sys.exit(1)

    def polling(self, monitor, interval_secs):
        """main polling function"""

        num_samples = 0
        sample_duration = 0
        num_pushes = 0
        push_check_duration = 0.0
        push_frequency_secs = self.__pushFrequencyMins * 60
        push_time_accumulation = 0.0
        interval_microsecs = int(interval_secs * 1000000)
        mem_mb_base = utils.getMemoryUsageMB()
        base_start_time = time.perf_counter()

        # ---
        # main sampling loop
        try:
            while not terminateFlagEvent.is_set():
                start_time = time.perf_counter()
                timestamp = datetime.now(timezone.utc)
                monitor.updateAllMetrics()
                self.getMetrics(timestamp)
                num_samples += 1
                sample_duration += time.perf_counter() - start_time

                if push_check_duration > push_frequency_secs:
                    push_check_duration = 0.0
                    if True:
                        try:
                            push_start_time = time.perf_counter()
                            self.dumpCache(mode="victoria")
                            self.__dataVM.clear()
                            num_pushes += 1
                            push_time_accumulation += time.perf_counter() - push_start_time
                        except:
                            pass

                self.sleep_microsecs(interval_microsecs)
                # time.sleep(interval_secs)
                push_check_duration += time.perf_counter() - start_time

        except KeyboardInterrupt:
            logging.info("")
            logging.info("Terminating data collection from keyboard interrupt.")

        # end sampling loop
        # ---

        duration_secs = time.perf_counter() - base_start_time

        if len(self.__dataVM) > 0:
            try:
                logging.info("Initiating final data push...")
                self.dumpCache(mode="victoria")
            except:
                pass

        logging.info("--> Sampling interval          = %.4f (secs)" % interval_secs)
        logging.info("--> Total # of samples         = %i" % num_samples)
        if num_samples > 0:
            logging.info("--> Average time/sample        = %.4f (secs)" % (sample_duration / num_samples))
        logging.info("--> Total data pushes          = %i" % num_pushes)
        if num_pushes > 0:
            logging.info("--> Average push duration      = %.4f (secs)" % (push_time_accumulation / num_pushes))
        # duration_secs = num_samples * interval_secs
        if duration_secs >= 3600:
            logging.info("--> Data collection duration   = %.4f (hours)" % (1.0 * duration_secs / 3600.0))
        elif duration_secs >= 60:
            logging.info("--> Data collection duration   = %.4f (mins)" % (1.0 * duration_secs / 60.0))
        else:
            logging.info("--> Data collection duration   = %.4f (secs)" % duration_secs)
        logging.info("--> Base memory use at start   = %.3f MB" % mem_mb_base)
        logging.info("--> Memory growth at stop      = %.3f MB" % (utils.getMemoryUsageMB() - mem_mb_base))

        # deliver event to shutdown procedure
        logging.debug("setting shutdown delivery event")
        dataDeliveredEvent.set()
        logging.debug("shutdown delivery event is set")
        time.sleep(0.5)

        logging.info("Terminating execution...")
        os.kill(os.getpid(), signal.SIGTERM)
        return


def parse_args():
    """Parse command-line arguments

    Returns:
        argparse.Namespace: parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", type=str, help="runtime config file", default=None)
    parser.add_argument("--interval", type=float, help="sampling frequency (in secs)", default=0.5)
    parser.add_argument("--logfile", type=str, help="redirect stdout to logfile", default=None)
    parser.add_argument("--endpoint", type=str, help="hostname of VictoriaMetrics server", default="localhost")
    parser.add_argument("--port", type=int, help="port to access VictoriaMetrics server", default=8428)

    return parser.parse_args()


@app.route("/shutdown")
def terminate():
    """Endpoint that can be used to terminate execution"""
    logging.info("Received shutdown request")
    terminateFlagEvent.set()

    # spin loop till notice recieved that last data was pushed
    maxChecks = 0
    while not dataDeliveredEvent.isSet():
        logging.debug("waiting for data delivery event...")
        maxChecks += 1
        if maxChecks > 100:
            break
        time.sleep(0.1)

    return jsonify({"message": "Shutting down..."}), 200


@app.route("/metrics")
def heartbeat():
    """Endpoint that can be used to confirm exporter is running"""
    return jsonify({"status": "ok"}), 200


def runFlask(config):
    listenPort = config["omnistat.collectors"].get("port", 8001)
    app.run(host="0.0.0.0", port=listenPort)


def main():

    args = parse_args()
    config = utils.readConfig(utils.findConfigFile(args.configfile))

    # Initialize GPU monitoring
    monitor = Monitor(config, logFile=args.logfile)
    monitor.initMetrics()

    # Initialize standalone polling
    if args.interval < 0.005:
        logging.error("")
        logging.error("[ERROR]: Please set sampling interval to be >= 5 millisecs (%s)" % args.interval)
        exit(1)

    caching = Standalone(args, config)
    caching.initMetrics()

    # Launch flask app as thread so we can respond to remote shutdown requests
    flask_thread = threading.Thread(target=runFlask, args=[config])
    flask_thread.start()

    # Initiate main polling loop/data collection
    caching.polling(monitor, args.interval)


if __name__ == "__main__":
    main()
