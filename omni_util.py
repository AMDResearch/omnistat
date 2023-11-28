#!/usr/bin/env python3
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
import argparse
import configparser
import logging
import sys
import os
import time
import utils
from pathlib import Path

class UserBasedMonitoring():
    def __init__(self):
        logging.basicConfig(
                format="%(message)s", level=logging.INFO, stream=sys.stdout
            )
        
        # read runtime config (file is required to exist)
        self.topDir = Path(__file__).resolve().parent
        configFile = str(self.topDir) + "/omniwatch.config"

        if os.path.isfile(configFile):
            logging.info("Reading runtime-config from %s" % configFile)
            self.runtimeConfig = configparser.ConfigParser()
            self.runtimeConfig.read(configFile)

        return

    def startPromServer(self,host='localhost'):
        if host == "localhost":
            logging.info("Starting prometheus server on localhost")

            section = 'omniwatch.promserver'
            ps_template = self.runtimeConfig[section].get('template','prometheus.yml.template')
            ps_binary = self.runtimeConfig[section].get('binary')
            ps_datadir = self.runtimeConfig[section].get('datadir','data_prom')
            ps_logfile = self.runtimeConfig[section].get('logfile','prom_server.log')

            command=[ps_binary,
                    "--config.file=%s" % ps_template,
                    "--storage.tsdb.path=%s" % ps_datadir
            ]
            utils.runBGProcess(command,outputFile=ps_logfile)
        # elif host == "slurm":
        #     # launch on *last* host assigned to this job
        #     logging.info("Starting prometheus server under slurm")
        else:
            utils.error("Unsupported host type for startPromServer (%s)" % host )

    def stopPromServer(self,host=None):
        if host == "localhost":
            logging.info("Stopping prometheus server on localhost")

            command=["pkill","-SIGTERM","-u","%s" % os.getuid(),"prometheus"]

            utils.runShellCommand(command)
            time.sleep(1)
        return

    def startExporters(self,host=None):
        binary = self.topDir / 'node_monitoring.py'
        logfile = self.runtimeConfig['omniwatch.collectors'].get('logfile','exporter.log')
        logging.info('Exporter binary = %s (logfile=%s)' % (binary,logfile))
        utils.runBGProcess(binary,outputFile=logfile)
        return
    
    def stopExporters(self):
        command=["pkill","-SIGINT","-f","-u","%s" % os.getuid(),"omniwatch/node_monitoring.py"]
        logging.info(command)
        utils.runShellCommand(command)
        time.sleep(1)
        return
    

def main():

    userUtils = UserBasedMonitoring()

    parser = argparse.ArgumentParser()
    parser.add_argument("--startserver", help="Start local prometheus server",action='store_true')
    parser.add_argument("--stopserver", help="Stop local prometheus server",action='store_true')
    parser.add_argument("--startexporters", help="Start data expporters",action='store_true') 
    parser.add_argument("--stopexporters", help="Stop data exporters",action='store_true') 

    args = parser.parse_args()
    
    host="localhost"
    #host="slurm"
    if args.startserver:
        userUtils.startPromServer()
    elif args.stopserver:
        userUtils.stopPromServer(host=host)
    elif args.startexporters:
        userUtils.startExporters()
    elif args.stopexporters:
        userUtils.stopExporters()


if __name__ == "__main__":
    main()