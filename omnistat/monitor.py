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

# Prometheus data collector for HPC systems.
#
# Supporting monitor class to implement a prometheus data collector with one 
# or more custom collector(s).
#--

import configparser
import importlib.resources
import logging
import os
import platform
import re
import sys

from pathlib import Path
from prometheus_client import generate_latest, CollectorRegistry

from omnistat import utils

class Monitor():
    def __init__(self,config):
        logging.basicConfig(
            format="%(message)s", level=logging.INFO, stream=sys.stdout
        )

        self.runtimeConfig = {}

        self.runtimeConfig['collector_enable_rocm_smi'] = config['omnistat.collectors'].getboolean('enable_rocm_smi',True)
        self.runtimeConfig['collector_enable_slurm'] = config['omnistat.collectors'].getboolean('enable_slurm',False)
        self.runtimeConfig['collector_enable_amd_smi'] = config['omnistat.collectors'].getboolean('enable_amd_smi', False)
        self.runtimeConfig['collector_enable_amd_smi_process'] = config['omnistat.collectors'].getboolean('enable_amd_smi_process',
                                                                                                            False)
        self.runtimeConfig['collector_port'] = config['omnistat.collectors'].get('port',8000)
        self.runtimeConfig['collector_usermode'] = config['omnistat.collectors'].getboolean('usermode',False)
        self.runtimeConfig['collector_rocm_path'] = config['omnistat.collectors'].get('rocm_path','/opt/rocm')

        allowed_ips = config['omnistat.collectors'].get('allowed_ips','127.0.0.1')
        # convert comma-separated string into list
        self.runtimeConfig['collector_allowed_ips'] = re.split(r',\s*',allowed_ips)
        logging.info("Allowed query IPs = %s" % self.runtimeConfig['collector_allowed_ips'])

        # additional slurm collector controls
        if self.runtimeConfig['collector_enable_slurm'] == True:
            self.jobDetection = {}
            self.runtimeConfig['slurm_collector_annotations'] = config['omnistat.collectors.slurm'].getboolean('enable_annotations',False)
            self.jobDetection['mode'] = config['omnistat.collectors.slurm'].get('job_detection_mode','file-based')
            self.jobDetection['file']= config['omnistat.collectors.slurm'].get('job_detection_file','/tmp/omni_slurmjobinfo')
            if config.has_option('omnistat.collectors.slurm','host_skip'):
                self.runtimeConfig['slurm_collector_host_skip'] = config['omnistat.collectors.slurm']['host_skip']

        # defined global prometheus metrics
        self.__globalMetrics = {}
        self.__registry_global = CollectorRegistry()

        # define desired collectors
        self.__collectors = []

        # allow for disablement of slurm collector via regex match
        if self.runtimeConfig['collector_enable_slurm']:
            if config.has_option('omnistat.collectors.slurm','host_skip'):
                host_skip = utils.removeQuotes(config['omnistat.collectors.slurm']['host_skip'])
                hostname = platform.node().split('.', 1)[0]
                p = re.compile(host_skip)
                if p.match(hostname):
                    self.runtimeConfig['collector_enable_slurm'] = False
                    logging.info("Disabling SLURM collector via host_skip match (%s)" % host_skip)

        logging.debug("Completed collector initialization (base class)")
        return

    def initMetrics(self):

        if self.runtimeConfig['collector_enable_rocm_smi']:
            from omnistat.collector_smi import ROCMSMI
            self.__collectors.append(ROCMSMI(rocm_path=self.runtimeConfig['collector_rocm_path']))
        if self.runtimeConfig['collector_enable_amd_smi']:
            from omnistat.collector_smi_v2 import AMDSMI
            self.__collectors.append(AMDSMI())
        if self.runtimeConfig['collector_enable_amd_smi_process']:
            from omnistat.collector_smi_process import AMDSMIProcess
            self.__collectors.append(AMDSMIProcess())
        if self.runtimeConfig['collector_enable_slurm']:
            from omnistat.collector_slurm import SlurmJob
            self.__collectors.append(SlurmJob(userMode=self.runtimeConfig['collector_usermode'],
                                              annotations=self.runtimeConfig['slurm_collector_annotations'],
                                              jobDetection=self.jobDetection))
        
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