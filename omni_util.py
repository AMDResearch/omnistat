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
import os
import subprocess
import sys
import time
import utils
import yaml
from pathlib import Path


class UserBasedMonitoring:
    def __init__(self):
        logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stdout)
        self.scrape_interval = 60  # default scrape interval in seconds
        self.timeout = 5           # default scrapte timeout in seconds
        return

    def setup(self):
        # read runtime config (file is required to exist)
        self.topDir = Path(__file__).resolve().parent
        configFile = str(self.topDir) + "/omniwatch.config"

        if os.path.isfile(configFile):
            logging.info("Reading runtime-config from %s" % configFile)
            self.runtimeConfig = configparser.ConfigParser()
            self.runtimeConfig.read(configFile)

        self.slurmHosts = self.getSlurmHosts()

    def setMonitoringInterval(self,interval):
        self.scrape_interval = int(interval)
        return

    def getSlurmHosts(self):
        hostlist = os.getenv("SLURM_JOB_NODELIST", None)
        if hostlist:
            results = utils.runShellCommand(["scontrol", "show", "hostname", hostlist])
            if results.stdout.strip():
                return results.stdout.splitlines()
            else:
                utils.error("Unable to detect assigned SLURM hosts from %s" % hostlist)
        else:
            logging.warning(
                "\nNo SLURM_JOB_NODELIST var detected - please verify running under active SLURM job.\n"
            )

    def startPromServer(self):
        logging.info("Starting prometheus server on localhost")
        scrape_interval = "%ss" %self.scrape_interval
        logging.info("--> sampling interval = %s" % scrape_interval)

        if self.timeout < self.scrape_interval:
            scrape_timeout = "5s"
        else:
            scrape_timeout = scrape_interval

        section = "omniwatch.promserver"
        ps_template = self.runtimeConfig[section].get(
            "template", "prometheus.yml.template"
        )
        ps_binary = self.runtimeConfig[section].get("binary")
        ps_datadir = self.runtimeConfig[section].get("datadir", "data_prom")
        ps_logfile = self.runtimeConfig[section].get("logfile", "prom_server.log")
        ps_corebinding = self.runtimeConfig[section].get("corebinding","0")

        # generate prometheus config file to scrape local exporters
        computes = {}
        computes["targets"] = []
        if self.slurmHosts:
            for host in self.slurmHosts:
                computes["targets"].append("%s:%s" % (host, 8001))

            prom_config = {}
            prom_config["scrape_configs"] = []
            prom_config["scrape_configs"].append(
                {
                    "job_name": "omniwatch",
                    "scrape_interval": scrape_interval,
                    "scrape_timeout": scrape_timeout,
                    "static_configs": [computes],
                }
            )
            with open("prometheus.yml", "w") as yaml_file:
                yaml.dump(prom_config, yaml_file, sort_keys=False)

            command = [
                "numactl","--physcpubind=%s" % ps_corebinding,
                ps_binary,
                "--config.file=%s" % "prometheus.yml",
                "--storage.tsdb.path=%s" % ps_datadir,
            ]
            utils.runBGProcess(command, outputFile=ps_logfile)
        else:
            utils.error("No compute hosts avail for startPromServer")

    def stopPromServer(self):
        logging.info("Stopping prometheus server on localhost")

        command = ["pkill", "-SIGTERM", "-u", "%s" % os.getuid(), "prometheus"]

        utils.runShellCommand(command,timeout=5)
        time.sleep(1)
        return

    def startExporters(self):
        port = self.runtimeConfig["omniwatch.collectors"].get("usermode_port", "8001")

        if self.slurmHosts:
            for host in self.slurmHosts:
                logging.info("Launching exporter on host -> %s" % host)
                logfile = "exporter.%s.log" % host
                logpath = self.topDir / logfile
                cmd = [
                    "gunicorn",
                    "-D",
                    "-b 0.0.0.0:%s" % port,
                    "--access-logfile %s" % (self.topDir / "access.log"),
                    "--capture-output",
                    "--log-file %s" % logpath,
                    "--pythonpath %s" % self.topDir,
                    "node_monitoring:app",
                ]

                base_ssh = ["ssh",host]
                logging.debug("-> running command: %s" % (base_ssh + cmd))
                #subprocess.run(base_ssh + cmd,timeout=5,exit_on_error=True)
                utils.runShellCommand(base_ssh + cmd,timeout=15,exit_on_error=True)
        return

    def stopExporters(self):
        # command=["pkill","-SIGINT","-f","-u","%s" % os.getuid(),"python.*omniwatch.*node_monitoring.py"]

        for host in self.slurmHosts:
            logging.info("Stopping exporter for host -> %s" % host)
            cmd = ["curl", "%s:%s/shutdown" % (host, "8001")]
            logging.debug("-> running command: %s" % cmd)
            #utils.runShellCommand(["ssh", host] + cmd)
            utils.runShellCommand(cmd,timeout=5)
        return


def main():
    userUtils = UserBasedMonitoring()

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
    parser.add_argument("--startserver", help="Start local prometheus server", action="store_true")
    parser.add_argument("--stopserver", help="Stop local prometheus server", action="store_true")
    parser.add_argument("--startexporters", help="Start data expporters", action="store_true")
    parser.add_argument("--stopexporters", help="Stop data exporters", action="store_true")
    parser.add_argument("--start",help="Start all necessary user-based monitoring services",action="store_true")
    parser.add_argument("--stop",help="Stop all user-based monitoring services",action="store_true")
    parser.add_argument("--interval",help="Monitoring sampling interval in secs (default=60)")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    userUtils.setup()
    if args.interval:
        userUtils.setMonitoringInterval(args.interval)

    if args.startserver:
        userUtils.startPromServer()
    elif args.stopserver:
        userUtils.stopPromServer()
    elif args.startexporters:
        userUtils.startExporters()
    elif args.stopexporters:
        userUtils.stopExporters()
    elif args.start:
        userUtils.startExporters()
        userUtils.startPromServer()
    elif args.stop:
        userUtils.stopPromServer()
        userUtils.stopExporters()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
