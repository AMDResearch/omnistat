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

import argparse
import configparser
import importlib.resources
import logging
import os
import platform
import re
import sys

from pathlib import Path

from prometheus_client import generate_latest, CollectorRegistry

import omniwatch.utils as utils

class Monitor():
    def __init__(self):
        logging.basicConfig(
            format="%(message)s", level=logging.INFO, stream=sys.stdout
        )

        # Resolve path to default config file in the current installation.
        # This configuration is only meant to provide sane defaults to run
        # locally, but most installations will need a custom file.
        # It can be overridden using the configFile option below.
        packageDir = importlib.resources.files("omniwatch")
        defaultConfigFile = packageDir.joinpath("config/omniwatch.default")

        parser = argparse.ArgumentParser()
        parser.add_argument("--configFile",type=str,
                            help=f"runtime config file (default={defaultConfigFile})",
                            default=defaultConfigFile)
        args = parser.parse_args()

        configFile = args.configFile
        self.runtimeConfig = {}

        if os.path.isfile(configFile):
            logging.info("Reading runtime-config from %s" % configFile)
            config = configparser.ConfigParser()
            config.read(configFile)

            self.runtimeConfig['collector_enable_rocm_smi'] = config['omniwatch.collectors'].getboolean('enable_rocm_smi',True)
            self.runtimeConfig['collector_enable_slurm'] = config['omniwatch.collectors'].getboolean('enable_slurm',False)
            self.runtimeConfig['slurm_collector_annotations'] = config['omniwatch.collectors.slurm'].getboolean('enable_annotations',False)
            self.runtimeConfig['collector_port'] = config['omniwatch.collectors'].get('port',8000)
            self.runtimeConfig['collector_usermode'] = config['omniwatch.collectors'].getboolean('usermode',False)
            self.runtimeConfig['collector_rocm_path'] = config['omniwatch.collectors'].get('rocm_path','/opt/rocm')

            # optional runtime controls
            if config.has_option('omniwatch.collectors.slurm','host_skip'):
                self.runtimeConfig['slurm_collector_host_skip'] = config['omniwatch.collectors.slurm']['host_skip']

        else:
            utils.error("Unable to find runtime config file %s" % configFile)

        # defined global prometheus metrics
        self.__globalMetrics = {}
        self.__registry_global = CollectorRegistry()

        # define desired collectors
        self.__collectors = []

        # allow for disablement of slurm collector via regex match
        if self.runtimeConfig['collector_enable_slurm']:
            if config.has_option('omniwatch.collectors.slurm','host_skip'):
                host_skip = utils.removeQuotes(config['omniwatch.collectors.slurm']['host_skip'])
                hostname = platform.node().split('.', 1)[0]
                p = re.compile(host_skip)
                if p.match(hostname):
                    self.runtimeConfig['collector_enable_slurm'] = False
                    logging.info("Disabling SLURM collector via host_skip match (%s)" % host_skip)

        logging.debug("Completed collector initialization (base class)")
        return

    def initMetrics(self):
        rocmSMI = True
        enableSLURM = True

        if self.runtimeConfig['collector_enable_rocm_smi']:
            from omniwatch.collector_smi import ROCMSMI
            self.__collectors.append(ROCMSMI(rocm_path=self.runtimeConfig['collector_rocm_path']))
        if self.runtimeConfig['collector_enable_slurm']:
            from omniwatch.collector_slurm import SlurmJob
            self.__collectors.append(SlurmJob(userMode=self.runtimeConfig['collector_usermode'],
                                              annotations=self.runtimeConfig['slurm_collector_annotations']))
        
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