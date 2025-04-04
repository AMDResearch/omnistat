# -------------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2023 - 2025 Advanced Micro Devices, Inc. All Rights Reserved.
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

"""Network monitoring

Implements a prometheus info metric to track network traffic data for interface
exposed in /sys/class/net

"""

import json
import logging
import os
import platform
import sys

from prometheus_client import Gauge

import omnistat.utils as utils
from omnistat.collector_base import Collector


class NETWORK(Collector):
    def __init__(self, annotations=False, jobDetection=None):
        logging.debug("Initializing networking data collector")
        self.__prefix = "network_"
        self.__nic_rx_data_paths = {}
        self.__nic_tx_data_paths = {}
        self.__metrics = {}


    def registerMetrics(self):
        """Register metrics of interest"""

        # scan local NICs 
        base_path = "/sys/class/net"
        for entry in os.listdir(base_path):
            if entry == "lo":
                continue
            nic_dir = os.path.join(base_path,entry)
            if os.path.isdir(nic_dir):
                rx_path = os.path.join("%s/statistics/rx_bytes" % nic_dir)
                if os.path.isfile(rx_path) and os.path.getsize(rx_path) > 0:
                    self.__nic_rx_data_paths[entry] = rx_path

                tx_path = os.path.join("%s/statistics/tx_bytes" % nic_dir)
                if os.path.isfile(tx_path) and os.path.getsize(tx_path) > 0:
                    self.__nic_tx_data_paths[entry] = (tx_path)                    

        if len(self.__nic_rx_data_paths) > 0:
            logging.debug(self.__nic_rx_data_paths)
            metricName="rx_bytes"
            description="Received (bytes)"
            self.__rx_metric = Gauge(self.__prefix + metricName,description,labelnames=["interface"])
            logging.info("--> [registered] %s -> %s (gauge)" % (metricName, description))

        if len(self.__nic_tx_data_paths) > 0:
            metricName="tx_bytes"
            description="Transmitted (bytes)"
            self.__tx_metric = Gauge(self.__prefix + metricName,description,labelnames=["interface"])
            logging.info("--> [registered] %s -> %s (gauge)" % (metricName, description))                        
            

    def updateMetrics(self):
        """Update registered metrics of interest"""
        
        # Received
        for nic, path in  self.__nic_rx_data_paths.items():
            try:
                with open(path, 'r') as f:
                    data = int(f.read().strip())
                    self.__rx_metric.labels(interface=nic).set(data)
            except:
                pass

        # Transmitted
        for nic, path in  self.__nic_tx_data_paths.items():
            try:
                with open(path, 'r') as f:
                    data = int(f.read().strip())
                    self.__tx_metric.labels(interface=nic).set(data)
            except:
                pass             

        return
