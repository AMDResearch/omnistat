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

from monitor import Monitor
from flask import Flask
from flask_prometheus_metrics import register_metrics
import sys

if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = None

app = Flask("omniwatch")
monitor = Monitor(configFilePath=config_file)
monitor.initMetrics()

# note: following shutdown procedure works with gunicorn only
def shutdown():
    sys.exit(4)

# Register metrics with Flask app
register_metrics(app, app_version="v0.1.0", app_config="production")

# Setup endpoint(s)
app.route("/metrics")(monitor.updateAllMetrics)
app.route("/shutdown")(shutdown)

# Run the main function
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=monitor.runtimeConfig['collector_port'])
