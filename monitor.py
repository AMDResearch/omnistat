# -------------------------------------------------------------------------------
# MIT License
# 
# Copyright (c) 2023 Advanced Micro Devices, Inc. All Rights Reserved.
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

# Prometheus data collector for HPC systems.
#
# Supporting monitor class to implement a prometheus data collector with one 
# more custom collector(s).
#--

import logging
import sys
import re
import platform
from prometheus_client import generate_latest, CollectorRegistry

class Monitor():
    def __init__(self):
        logging.basicConfig(
            format="%(message)s", level=logging.INFO, stream=sys.stdout
        )
        # defined GPU prometheus metrics (stored on a per-gpu basis)
        # self.__GPUmetrics = {}
 
        # defined global prometheus metrics
        self.__globalMetrics = {}
        self.__registry_global = CollectorRegistry()
        # Resource manager type
        self.__rms = "slurm"

        # define desired collectors
        self.__collectors = []

        self.enableROCmCollector = True
        self.enableSLURMCollector = True

        # allow for disablement of slurm collector via regex match
        SLURM_host_skip="login.*"
        hostname = platform.node().split('.', 1)[0]
        p = re.compile(SLURM_host_skip)
        if p.match(hostname):
            self.enableSLURMCollector = False

        logging.debug("Completed collector initialization (base class)")
        return

    def initMetrics(self):
        rocmSMI = True
        enableSLURM = True

        if self.enableROCmCollector:
            from collectors import ROCMSMI
            self.__collectors.append(ROCMSMI())
        if self.enableSLURMCollector:
            from collectors import SlurmJob
            self.__collectors.append(SlurmJob())
        
        # Initialize all metrics
        for collector in self.__collectors:
            collector.registerMetrics()

        # Gather metrics on startup
        for collector in self.__collectors:
            collector.updateMetrics()

    def updateAllMetrics(self):
        for collector in self.__collectors:
            collector.updateMetrics()
        return generate_latest()