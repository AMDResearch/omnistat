# Prometheus data collector for HPC systems.
# --> intended for use with resource manager prolog/epilog hooks
# --> two primary data collection points are defined
#     (1) global - at job begin/end
#     (2) incremental - periodically executed during job execution
#
# Assumptions:
#   * user job has exclusive allocation to host
#   * desired metrics to collect do not change during a given user job
#   * polling frequency is desired to be controlled externally
# ---

import subprocess
import json
import logging
import sys
from monitor import Monitor
from flask import Flask
from flask_prometheus_metrics import register_metrics
from prometheus_client import Gauge, generate_latest, CollectorRegistry

# class Metrics:
#     def __init__(self):
#         logging.basicConfig(
#             format="%(message)s", level=logging.DEBUG, stream=sys.stdout
#         )
#         # defined GPU prometheus metrics (stored on a per-gpu basis)
#         self.__GPUmetrics = {}
#         # command-line lflags for use with rocm-smi to obtained desired metrics
#         self.__rocm_smi_flags = "-P -u -f -t --showmeminfo vram --json"
#         # list of desired metrics to query: (prometheus_metric_name -> rocm-smi-key)
#         self.__rocm_smi_metrics = {
#             "temp_die_edge": "Temperature (Sensor edge) (C)",
#             "avg_pwr": "Average Graphics Package Power (W)",
#             "utilization": "GPU use (%)",
#             "vram_total": "VRAM Total Memory (B)",
#             "vram_used": "VRAM Total Used Memory (B)",
#         }
#         # defined global prometheus metrics
#         self.__globalMetrics = {}
#         self.__registry_global = CollectorRegistry()
#         # Resource manager type
#         self.__rms = "slurm"

#     def initMetrics(self):
#         self.global_metrics_register()
#         self.rocm_smi_register()

#     def registerGPUMetric(self, gpu, name, type, description):
#         # encode gpu in name for uniqueness
#         metricName = gpu + "_" + name
#         if metricName in self.__GPUmetrics[gpu]:
#             logging.error(
#                 "Ignoring duplicate metric name addition: %s (gpu=%s)" % (name, gpu)
#             )
#             return
#         if type == "gauge":
#             self.__GPUmetrics[gpu][metricName] = Gauge(metricName, description)
#             logging.info(
#                 "  --> [registered] %s -> %s (gauge)" % (metricName, description)
#             )
#         else:
#             logging.error("Ignoring unknown metric type -> %s" % type)
#         return

#     def global_metrics_register(self):
#         # jobID
#         labels = ['userid']
#         self.__globalMetrics["jobid"] = Gauge(
#             "jobid", "Job Identifier", labels, registry=self.__registry_global
#         )

#         labels = ['unknown']
#         #self.__globalMetrics["jobid"].set(-1)
#         self.__globalMetrics["jobid"].labels(labels).set(-1)

#     def get_metrics_global(self):
#         # self.collect_data_global()
#         return generate_latest(self.__registry_global)

#     def get_metrics_incremental(self):
#         self.collect_data_incremental()
#         # incremental query returns all known metrics
#         return generate_latest()


# Main function to run the application
def main():

    
    monitor = Monitor()
    monitor.initMetrics()

    # monitor = Metrics()
    # monitor.initMetrics()

    # Register metrics with Flask app
    app = Flask("omniwatch")
    register_metrics(app, app_version="v0.1.0", app_config="production")

    app.route("/metrics")(monitor.updateAllMetrics)

    # # Define incremental metrics
    # monitor.collect_data_incremental()

    # # Define http query endpoints
    # app.route("/metrics_inc")(monitor.get_metrics_incremental)
    #    app.route("/metrics_global")(monitor.get_metrics_global)

    app.run(host="0.0.0.0", port=8000)


# Run the main function
if __name__ == "__main__":
    main()
