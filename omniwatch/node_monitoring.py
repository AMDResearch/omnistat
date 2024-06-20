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
# --> intended for two primary usage modes:
#     - system-mode (collect data continuously on all compute hosts)
#     - user-mode (user spawns data collection within a specific job)
#
# Assumptions:
#   * user job has exclusive allocation to host
#   * desired metrics to collect do not change during a given user job
#   * polling frequency is desired to be controlled externally
# ---

import sys

from flask import Flask, request, abort, jsonify
from flask_prometheus_metrics import register_metrics

from omniwatch.monitor import Monitor

# note: following shutdown procedure works with gunicorn only
def shutdown():
    sys.exit(4)

app = Flask("omniwatch")
monitor = Monitor()
monitor.initMetrics()

# Register metrics with Flask app
register_metrics(app, app_version="v0.1.0", app_config="production")

# Setup endpoint(s)
app.route("/metrics")(monitor.updateAllMetrics)
app.route("/shutdown")(shutdown)

# Enforce network restrictions
@app.before_request
def restrict_ips():
    if '0.0.0.0' in monitor.runtimeConfig['collector_allowed_ips']:
        return
    elif request.remote_addr not in monitor.runtimeConfig['collector_allowed_ips']:
        abort(403)

@app.errorhandler(403)
def forbidden(e):
    return jsonify(error="Access denied"), 403

# Run the main function
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=monitor.runtimeConfig['collector_port'])
