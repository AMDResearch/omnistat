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

import argparse
import configparser
import os
import signal
import sys
import gunicorn.app.base
from flask import Flask, request, abort, jsonify
from flask_prometheus_metrics import register_metrics
from monitor import Monitor

def shutdown():
    os.kill(os.getppid(), signal.SIGTERM)
    return jsonify({'message': 'Shutting down...'}), 200

def readRuntimeConfig(configFile):
    if os.path.isfile(configFile):
        print("Reading runtime-config from %s" % configFile)
        config = configparser.ConfigParser()
        config.read(configFile)
        return(config)
    else:
        print("[ERROR]: unable to open runtime config file -> %s" % configFile)
        sys.exit(1)

class OmniStatServer(gunicorn.app.base.BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--configFile",type=str,
                            help="runtime config file (default=omniwatch.default)",
                            default="omniwatch/config/omniwatch.default")
    args = parser.parse_args()
    config = readRuntimeConfig(args.configFile)

    # Setup Flask app for data collection
    app = Flask("omnistat")
    monitor = Monitor(config)
    monitor.initMetrics()

    register_metrics(app, app_version="v0.1.0", app_config="production")
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

    listenPort = config['omniwatch.collectors'].get('port',8000)
    options = {
        'bind': '%s:%s' % ('127.0.0.1', listenPort),
        'workers': 2,
    }

    # Launch gunicorn
    OmniStatServer(app, options).run()
