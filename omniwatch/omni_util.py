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

import argparse
import configparser
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
import yaml

from pathlib import Path

from pssh.clients import ParallelSSHClient

from omniwatch import utils

class UserBasedMonitoring:
    def __init__(self):
        logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stdout)
        self.scrape_interval = 60  # default scrape interval in seconds
        self.timeout = 5           # default scrape timeout in seconds
        self.use_pdsh = False      # whether to use pdsh for parallel exporter launch

        return

    def setup(self, configFile):
        # If configFile hasn't been explicitly set in the command line, attempt
        # to get a different configuration file from a different source.
        if configFile == None:
            configFile = utils.getConfigFile()
        elif not os.path.isfile(configFile):
            utils.error(f"Unable to find configuration file: {configFile}")

        self.configFile = configFile

        logging.info(f"Reading runtime-config from {self.configFile}")
        self.runtimeConfig = configparser.ConfigParser()
        self.runtimeConfig.read(self.configFile)

        self.slurmHosts = self.getSlurmHosts()

    def setMonitoringInterval(self, interval):
        self.scrape_interval = int(interval)
        return

    def enable_pdsh(self):
        self.use_pdsh = True
        return

    def getSlurmHosts(self):
        hostlist = os.getenv("SLURM_JOB_NODELIST", None)
        if hostlist:
            results = utils.runShellCommand(["scontrol", "show", "hostname", hostlist], timeout=10)
            if results.stdout.strip():
                return results.stdout.splitlines()
            else:
                utils.error("Unable to detect assigned SLURM hosts from %s" % hostlist)
        else:
            logging.warning("\nNo SLURM_JOB_NODELIST var detected - please verify running under active SLURM job.\n")

    def startPromServer(self):
        logging.info("Starting prometheus server on localhost")
        scrape_interval = "%ss" % self.scrape_interval
        logging.info("--> sampling interval = %s" % scrape_interval)

        if self.timeout < self.scrape_interval:
            scrape_timeout = "5s"
        else:
            scrape_timeout = scrape_interval

        section = "omniwatch.promserver"
        ps_binary = self.runtimeConfig[section].get("binary")
        ps_datadir = self.runtimeConfig[section].get("datadir", "data_prom", vars=os.environ)

        # datadir can be overridden by separate env variable
        if "OMNIWATCH_PROMSERVER_DATADIR" in os.environ:
            ps_datadir = os.getenv("OMNIWATCH_PROMSERVER_DATADIR")

        ps_logfile = self.runtimeConfig[section].get("logfile", "prom_server.log")
        ps_corebinding = self.runtimeConfig[section].get("corebinding", "0")

        # check if remote_write is desired
        remoteWrite = self.runtimeConfig[section].getboolean("remote_write", False)
        if remoteWrite:
            remoteWriteConfig = {}
            remoteWriteConfig["url"] = self.runtimeConfig[section].get("remote_write_url", "unknown")
            remoteWriteConfig["auth_user"] = self.runtimeConfig[section].get("remote_write_basic_auth_user", "user")
            remoteWriteConfig["auth_cred"] = self.runtimeConfig[section].get(
                "remote_write_basic_auth_cred", "credential"
            )
            logging.debug("Remote write url:  %s" % remoteWriteConfig["url"])
            logging.debug("Remote write user: %s" % remoteWriteConfig["auth_user"])

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
            if remoteWrite:
                auth = {
                    "username": remoteWriteConfig["auth_user"],
                    "password": remoteWriteConfig["auth_cred"],
                }

                prom_config["remote_write"] = []
                prom_config["remote_write"].append({"url": remoteWriteConfig["url"], "basic_auth": auth})

            with open("prometheus.yml", "w") as yaml_file:
                yaml.dump(prom_config, yaml_file, sort_keys=False)

            command = [
                "numactl",
                "--physcpubind=%s" % ps_corebinding,
                ps_binary,
                "--config.file=%s" % "prometheus.yml",
                "--storage.tsdb.path=%s" % ps_datadir,
            ]
            logging.debug("Server start command: %s" % command)
            utils.runBGProcess(command, outputFile=ps_logfile)
        else:
            utils.error("No compute hosts avail for startPromServer")

    def stopPromServer(self):
        logging.info("Stopping prometheus server on localhost")

        command = ["pkill", "-SIGTERM", "-u", "%s" % os.getuid(), "prometheus"]

        utils.runShellCommand(command, timeout=5)
        time.sleep(1)
        return

    def startExporters(self):
        port = self.runtimeConfig["omniwatch.collectors"].get("usermode_port", "8001")
        corebinding = self.runtimeConfig["omniwatch.collectors"].get("corebinding", "1")

        if self.slurmHosts:
            if self.use_pdsh:
                logging.info("Saving SLURM job state locally to compute hosts...")
                numNodes = os.getenv("SLURM_JOB_NUM_NODES")
                cmd = [
                    "srun",
                    "-N %s" % numNodes,
                    "--ntasks-per-node=1",
                    "%s/bin/python -m omniwatch.slurm_env" % sys.prefix,
                    "%s" % self.runtimeConfig["omniwatch.collectors.slurm"].get("job_detection_file")
                ]
                utils.runShellCommand(cmd, timeout=35, exit_on_error=True)

                logging.info("Launching exporters in parallel using pdsh")

                client = ParallelSSHClient(self.slurmHosts, allow_agent=False, timeout=120)
                gunicorn_path = f"{sys.prefix}/bin/gunicorn"

                # cmd = "gunicorn -D -b 0.0.0.0:%s --error-logfile %s --capture-output --pythonpath %s node_monitoring:app" % (port,self.topDir / "error.log" ,self.topDir)
                cmd = "%s -D -b 0.0.0.0:%s omniwatch.node_monitoring:app" % (gunicorn_path, port)

                output = client.run_command(cmd)

                # verify exporter available on all nodes...
                psecs = 6
                logging.info("Exporters launched, pausing for %i secs" % psecs)
                time.sleep(psecs)  # <-- needed for slow SLURM query times on ORNL
                numHosts = len(self.slurmHosts)
                numAvail = 0

                logging.info("Testing exporter availability")
                delay_start = 0.05
                for host in self.slurmHosts:
                    host_ok = False
                    for iter in range(1, 25):
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            result = s.connect_ex((host, int(port)))
                            if result == 0:
                                numAvail = numAvail + 1
                                logging.debug("Exporter on %s ok" % host)
                                host_ok = True
                                break
                            else:
                                delay = delay_start * iter
                                logging.debug("Retrying %s (sleeping for %.2f sec)" % (host, delay))
                                time.sleep(delay)
                            s.close()

                    if not host_ok:
                        logging.error("Missing exporter on %s (%s)" % (host, result))

                logging.info("%i of %i exporters available" % (numAvail, numHosts))
                if numAvail == numHosts:
                    logging.info("User mode data collectors: SUCCESS")

            else:
                # Launch with serialized ssh
                for host in self.slurmHosts:
                    logging.info("Launching exporter on host -> %s" % host)
                    logfile = "exporter.%s.log" % host
                    logpath = self.topDir / logfile

                    # overwrite logfile
                    if os.path.exists(logpath):
                        os.remove(logpath)

                    use_gunicorn = True
                    if use_gunicorn:
                        cmd = [
                            "numactl",
                            "--physcpubind=%s" % corebinding,
                            "nice",
                            "-n 20",
                            "%s/bin/gunicorn" % sys.prefix,
                            "-e OMNIWATCH_CONFIG=%s" % self.configFile,
                            "-D",
                            "-b 0.0.0.0:%s" % port,
                            #                    "--access-logfile %s" % (self.topDir / "access.log"),
                            #                        "--threads 4",
                            "--capture-output",
                            "--log-file %s" % logpath,
                            "omniwatch.node_monitoring:app",
                        ]
                        base_ssh = ["ssh", host]
                        logging.debug("-> running command: %s" % (base_ssh + cmd))
                        utils.runShellCommand(base_ssh + cmd, timeout=25, exit_on_error=False)
                    else:
                        cmd = ["ssh", host, "%s/bin/python -m omniwatch.node_monitoring" % sys.prefix]
                        logging.debug("-> running command: %s" % (cmd))
                        utils.runBGProcess(cmd, outputFile=logfile)

        return

    def stopExporters(self):
        # command=["pkill","-SIGINT","-f","-u","%s" % os.getuid(),"python.*omniwatch.*node_monitoring.py"]

        for host in self.slurmHosts:
            logging.info("Stopping exporter for host -> %s" % host)
            cmd = ["curl", "%s:%s/shutdown" % (host, "8001")]
            logging.debug("-> running command: %s" % cmd)
            # utils.runShellCommand(["ssh", host] + cmd)
            utils.runShellCommand(cmd, timeout=5)
        return


def main():
    userUtils = UserBasedMonitoring()

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
    parser.add_argument("--configFile",type=str, help="runtime config file", default=None)
    parser.add_argument("--startserver", help="Start local prometheus server", action="store_true")
    parser.add_argument("--stopserver", help="Stop local prometheus server", action="store_true")
    parser.add_argument("--startexporters", help="Start data expporters", action="store_true")
    parser.add_argument("--stopexporters", help="Stop data exporters", action="store_true")
    parser.add_argument("--start", help="Start all necessary user-based monitoring services", action="store_true")
    parser.add_argument("--stop", help="Stop all user-based monitoring services", action="store_true")
    parser.add_argument("--interval", help="Monitoring sampling interval in secs (default=60)")
    parser.add_argument("--use_pdsh", help="Use pdsh utility to launch exporters in parallel (default mode)", default=True,action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    userUtils.setup(args.configFile)
    if args.interval:
        userUtils.setMonitoringInterval(args.interval)
    if args.use_pdsh:
        userUtils.enable_pdsh()

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
