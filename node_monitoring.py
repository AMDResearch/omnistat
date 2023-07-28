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
from flask import Flask
from flask_prometheus_metrics import register_metrics
from prometheus_client import Gauge, generate_latest
import json
import logging
import sys

# # Create Gauge metrics
# metric1 = Gauge("metric1_name", "Description of metric 1")
# metric2 = Gauge("metric2_name", "Description of metric 2")

def runShellCommand(command,capture_output=True,text=True,exit_on_error=False):
    """run a provided shell command

    Args:
        command (list): shell command to execute
        capture_output (bool, optional): _description_. Defaults to True.
        text (bool, optional): _description_. Defaults to True.
        exit_on_error (bool, optional): _description_. Defaults to False.
    """

    logging.debug("Command to run = %s" % command)
    results = subprocess.run(command, capture_output=capture_output, text=text)
    if exit_on_error and results.returncode != 0:
        logging.error("ERROR: Command failed")
        logging.error("       %s" % command)
        logging.error("stdout: %s" % results.stderr)
        logging.error("stderr: %s" % results.stderr)
        sys.exit(1)
    return(results)

class Metrics:
    def __init__(self):
        logging.basicConfig(
            format="%(message)s", level=logging.DEBUG, stream=sys.stdout
        )

        # defined GPU prometheus metrics (stored on a per-gpu basis)
        self.__GPUmetrics = {}  
        # command-line lflags for use with rocm-smi to obtained desired metrics 
        self.__rocm_smi_flags = "-P -u -f -t --showmeminfo vram --json"
        # list of desired metrics to query: (prometheus_metric_name -> rocm-smi-key)
        self.__rocm_smi_metrics = {
            'temp_die_edge':'Temperature (Sensor edge) (C)',
            'avg_pwr':'Average Graphics Package Power (W)',
            'utilization':'GPU use (%)',
            'vram_total':'VRAM Total Memory (B)',
            'vram_used':'VRAM Total Used Memory (B)',
        }

    def initMetrics(self):
        self.rocm_smi_register()

    def registerGPUMetric(self,gpu,name,type,description):
        # encode gpu in name for uniqueness
        metricName = gpu + '_' + name
        if metricName in self.__GPUmetrics[gpu]:
            logging.error("Ignoring duplicate metric name addition: %s (gpu=%s)" % (name,gpu))
            return
        if type == "gauge":
            self.__GPUmetrics[gpu][metricName] = Gauge(metricName,description)
            logging.info("  --> [registered] %s -> %s (gauge)" % (metricName,description))
        else:
            logging.error("Ignoring unknown metric type -> %s" % type)
        return 

    def rocm_smi_register(self):
        """Run rocm-smi and register metrics of interest"""

        command = ["rocm-smi"] + self.__rocm_smi_flags.split()
        data = runShellCommand(command,exit_on_error=True)
        data = json.loads(data.stdout)
        #desiredMetrics = [x[1] for x in self.__rocm_smi_metrics]
        for gpu in data:
            logging.debug("%s: gpu detected" % gpu)

            # init storage per gpu
            self.__GPUmetrics[gpu] = {}
            
            # look for matching metrics and register
            for metric in self.__rocm_smi_metrics:
                rocmName = self.__rocm_smi_metrics[metric]
                #if metric[1] in data[gpu]:
                if rocmName in data[gpu]:
                    self.registerGPUMetric(gpu,metric,'gauge',rocmName)
                    #self.registerGPUMetric(gpu,metric[0],'gauge',metric[1])
                else:
                    logging.info("   --> desired metric [%s] not available" % rocmName)
            # also highlight metrics not being used
            for key in data[gpu]:
                if key not in self.__rocm_smi_metrics.values():
                    logging.info("  --> [  skipping] %s" % key)
        return

    def collect_data_incremental(self):
        command = ["rocm-smi"] + self.__rocm_smi_flags.split()
        data = runShellCommand(command)
        try: 
            data = json.loads(data.stdout)
        except:
            return

        for gpu in self.__GPUmetrics:
            for metric in self.__GPUmetrics[gpu]:
                metricName = metric.removeprefix(gpu + '_')
                rocmName = self.__rocm_smi_metrics[metricName]
                if rocmName in data[gpu]:
                    value = data[gpu][rocmName]
                    self.__GPUmetrics[gpu][metric].set(value)
                    logging.debug("updated: %s = %s" % (metric,value))
        return
    
    def get_metrics_incremental(self):
        self.collect_data_incremental()
        return generate_latest()

# Function to collect data for metric 2
def collect_data_metric2():
    # Run your system command to collect data for metric 2
    ##     data = subprocess.run(['command_metric2', 'arg1', 'arg2'], capture_output=True, text=True)
    ##     return data.stdout.strip()
    return 345


# # Endpoint handler for metric 1
# @app.route("/metric_global")
# def get_metric1():
#     data = collect_data_metric1()
#     metric1.set(data)
#     return generate_latest(metric1)


# # Endpoint handler for metric 2
# @app.route("/metric2")
# def get_metric2():
#     #data = collect_data_metric2()
#     #metric2.set(data)
#     monitor.colle
#     return generate_latest(metric2)


# Main function to run the application
def main():
    monitor = Metrics()
    monitor.initMetrics()

    # Register metrics with Flask app
    app = Flask("omniwatch")
    register_metrics(app, app_version="v0.1.0", app_config="production")

    # Define incremental metrics
    monitor.collect_data_incremental()

    # Define http query endpoints
    app.route('/metric_inc')(monitor.get_metrics_incremental)

    app.run(host='0.0.0.0', port=8000)


# Run the main function
if __name__ == "__main__":
    main()
