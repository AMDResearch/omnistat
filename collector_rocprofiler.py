import logging
import os
import sys

from flask import Flask
from flask_prometheus_metrics import register_metrics

from prometheus_client import Gauge, generate_latest

from collector_base import Collector
from pyrocprofiler import DeviceSession

METRIC_NAMES = ["GRBM_COUNT", "GRBM_GUI_ACTIVE"]

logging.getLogger().setLevel(logging.INFO)

class rocprofiler(Collector):
    def __init__(self):
        logging.debug("Initializing rocprofiler data collector")
        self.__session = DeviceSession()
        self.__session.create(METRIC_NAMES)
        self.__metrics = []
        logging.info("pyrocprofiler initialized")

    def registerMetrics(self):
        prefix = "card0_rocprofiler_"
        for name in METRIC_NAMES:
            metric_name = prefix + name
            self.__metrics.append(Gauge(metric_name, ""))
            logging.info("  --> [registered] %s (counter)" % (metric_name))
        self.__session.start()

    def updateMetrics(self):
        metrics = self.__session.poll()
        for i, _ in enumerate(METRIC_NAMES):
            self.__metrics[i].set(metrics[i])
        return generate_latest()

def shutdown():
    sys.exit(4)

app = Flask("omniwatch-rocprofiler")
monitor = rocprofiler()
monitor.registerMetrics()

register_metrics(app, app_version="v0.1.0", app_config="production")

app.route("/metrics")(monitor.updateMetrics)
app.route("/shutdown")(shutdown)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port="10090")
