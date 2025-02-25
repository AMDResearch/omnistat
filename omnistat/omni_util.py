#!/usr/bin/env python3
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

import argparse
import getpass
import importlib.resources
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

# Use libssh instead of the default libssh2 to avoid issues with certain keys
# and newer versions of SSH.
from pssh.clients.ssh.parallel import ParallelSSHClient

from omnistat import utils


class UserBasedMonitoring:
    def __init__(self):
        logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stdout)
        self.scrape_interval = 30  # default scrape interval in seconds
        self.timeout = 5  # default scrape timeout in seconds
        self.__hosts = None
        self.__RMS_Detected = False

    def setup(self, configFileArgument):
        self.configFile = utils.findConfigFile(configFileArgument)
        self.runtimeConfig = utils.readConfig(self.configFile)

        # Path to Omnistat's executable scripts. For source deployments, this
        # is the top directory of a working copy of Omnistat. For package
        # deployments, it's the `bin` directory of the Python environment. By
        # resolving the path to `sys.argv[0]`, we ensure commands executed in
        # other nodes/environments use the same deployment and path as the
        # current local execution.
        self.binDir = Path(sys.argv[0]).resolve().parent

    def setMonitoringInterval(self, interval):
        self.scrape_interval = float(interval)
        return

    def rmsDetection(self):
        """Query environment to infer resource manager"""

        if self.__RMS_Detected:
            return

        if "SLURM_JOB_NODELIST" in os.environ:
            self.__rms = "slurm"
        elif "FLUX_URI" in os.environ:
            self.__rms = "flux"
        else:
            utils.error("Unknown/unsupported resource manager")
        logging.info("RMS detected = %s" % self.__rms)

        self.getRMSHosts()
        self.__RMS_Detected = True

        return

    def getRMSHosts(self):
        if self.__rms == "slurm":
            hostlist = os.getenv("SLURM_JOB_NODELIST", None)
            if hostlist:
                results = utils.runShellCommand(["scontrol", "show", "hostname", hostlist], timeout=10)
                if results.stdout.strip():
                    self.__hosts = results.stdout.splitlines()
                    # return results.stdout.splitlines()
                    return
                else:
                    utils.error("Unable to detect assigned SLURM hosts from %s" % hostlist)
            else:
                logging.warning(
                    "\nNo SLURM_JOB_NODELIST var detected - please verify running under active SLURM job.\n"
                )
        elif self.__rms == "flux":
            results = utils.runShellCommand(["flux", "hostlist", "local", "-e", "-d", ","])
            if results.stdout.strip():
                self.__hosts = results.stdout.strip().split(",")
                return
            else:
                utils.error("Unable to detect assigned Flux hosts.")
        else:
            utils.error("Unsupported RMS.")

    def startVictoriaServer(self):
        logging.info("Starting VictoriaMetrics server on localhost")
        section = "omnistat.usermode"
        vm_binary = self.runtimeConfig[section].get("victoria_binary")
        vm_datadir = self.runtimeConfig[section].get("victoria_datadir", "data_prom", vars=os.environ)

        if not os.path.exists(vm_binary):
            logging.error("")
            logging.error("[ERROR]: Unable to resolve path to VictoriaMetrics binary -> %s" % vm_binary)
            logging.error('[ERROR]: Please verify setting for "victoria_binary" in runtime configfile.')
            sys.exit(1)

        # datadir can be overridden by separate env variable
        if "OMNISTAT_VICTORIA_DATADIR" in os.environ:
            vm_datadir = os.getenv("OMNISTAT_VICTORIA_DATADIR")
        elif "OMNISTAT_VICSERVER_DATADIR" in os.environ:
            vm_datadir = os.getenv("OMNISTAT_VICSERVER_DATADIR")
            logging.warning(
                "OMNISTAT_VICSERVER_DATADIR variable is being deprecated - please use OMNISTAT_VICTORIA_DATADIR instead"
            )

        vm_logfile = self.runtimeConfig[section].get("victoria_logfile", "victoria_server.log")
        vm_corebinding = self.runtimeConfig[section].getint("victoria_corebinding", None)
        # corebinding can also be overridden by separate env variable
        if "OMNISTAT_VICTORIA_COREBINDING" in os.environ:
            vm_corebinding = int(os.getenv("OMNISTAT_VICTORIA_COREBINDING"))
            logging.info("--> Overriding corebinding setting using OMNISTAT_VICTORIA_COREBINDING=%i" % vm_corebinding)

        command = [
            vm_binary,
            "--storageDataPath=%s" % vm_datadir,
            "-memory.allowedPercent=10",
            "-retentionPeriod=10y",
            "-search.disableCache",
            "-httpListenAddr=:9090",
        ]
        envAddition = {}
        # restrict thread usage
        envAddition["GOMAXPROCS"] = "4"

        # optional NUMA setup
        numa_command = self.verifyNumaCommand(vm_corebinding)
        if numa_command:
            command = numa_command + command
        else:
            logging.info("Skipping VictoriaMetrics corebinding")

        logging.info("Server start command: %s" % command)
        utils.runBGProcess(command, outputFile=vm_logfile, envAdds=envAddition)

    def startPromServer(self, victoriaMode=False):

        if victoriaMode:
            self.startVictoriaServer()
            return

        self.rmsDetection()

        logging.info("Starting prometheus server on localhost")
        if self.scrape_interval >= 1:
            scrape_interval = "%ss" % int(self.scrape_interval)
        else:
            scrape_interval = "0s%sms" % int(self.scrape_interval * 1000)
        logging.info("--> sampling interval = %s" % scrape_interval)

        if self.timeout < self.scrape_interval:
            scrape_timeout = "5s"
        else:
            scrape_timeout = scrape_interval

        section = "omnistat.usermode"
        ps_binary = self.runtimeConfig[section].get("prometheus_binary")
        ps_datadir = self.runtimeConfig[section].get("prometheus_datadir", "data_prom", vars=os.environ)

        # datadir can be overridden by separate env variable
        if "OMNISTAT_PROMSERVER_DATADIR" in os.environ:
            ps_datadir = os.getenv("OMNISTAT_PROMSERVER_DATADIR")

        ps_logfile = self.runtimeConfig[section].get("prometheus_logfile", "prom_server.log")
        ps_corebinding = self.runtimeConfig[section].getint("prometheus_corebinding", None)
        # corebinding can also be overridden by separate env variable
        if "OMNISTAT_PROMSERVER_COREBINDING" in os.environ:
            ps_corebinding = int(os.getenv("OMNISTAT_PROMSERVER_COREBINDING"))

        # generate prometheus config file to scrape local exporters
        computes = {}
        computes["targets"] = []
        port = self.runtimeConfig["omnistat.collectors"].get("port", "8001")
        if self.__hosts:
            for host in self.__hosts:
                computes["targets"].append("%s:%s" % (host, port))

            prom_config = {}
            prom_config["scrape_configs"] = []
            prom_config["scrape_configs"].append(
                {
                    "job_name": "omnistat",
                    "scrape_interval": scrape_interval,
                    "scrape_timeout": scrape_timeout,
                    "static_configs": [computes],
                }
            )

            with open("prometheus.yml", "w") as yaml_file:
                yaml.dump(prom_config, yaml_file, sort_keys=False)

            command = [
                ps_binary,
                "--config.file=%s" % "prometheus.yml",
                "--storage.tsdb.path=%s" % ps_datadir,
            ]

            # optional NUMA setup
            numa_command = self.verifyNumaCommand(ps_corebinding)
            if numa_command:
                command = numa_command + command
            else:
                logging.info("Skipping Prometheus corebinding")

            logging.debug("Server start command: %s" % command)
            utils.runBGProcess(command, outputFile=ps_logfile)
        else:
            utils.error("No compute hosts avail for startPromServer")

    def stopPromServer(self, victoriaMode=False):
        if victoriaMode:
            logging.info("Stopping VictoriaMetrics server on localhost")

            command = ["pkill", "-f", "-SIGTERM", "-u", "%s" % os.getuid(), "victoria-metrics.*storageDataPath"]
            utils.runShellCommand(command, timeout=5)
            time.sleep(1)
            return
        else:
            logging.info("Stopping prometheus server on localhost")

            command = ["pkill", "-SIGTERM", "-u", "%s" % os.getuid(), "prometheus"]

            utils.runShellCommand(command, timeout=5)
            time.sleep(1)
            return

    def startExporters(self, victoriaMode=False):
        port = self.runtimeConfig["omnistat.collectors"].get("port", "8001")
        ssh_key = self.runtimeConfig["omnistat.usermode"].get("ssh_key", "~/.ssh/id_rsa")
        corebinding = self.runtimeConfig["omnistat.usermode"].getint("exporter_corebinding", None)

        self.rmsDetection()

        if victoriaMode:
            if os.path.exists("./exporter.log"):
                os.remove("./exporter.log")
            logging.info("[exporter]: Standalone sampling interval = %s" % self.scrape_interval)
            hostname = platform.node().split(".", 1)[0]
            cmd = f"nice -n 20 {sys.executable} -m omnistat.standalone --configfile={self.configFile} --interval {self.scrape_interval} --endpoint {hostname} --log exporter.log"
        else:
            cmd = f"nice -n 20 {sys.executable} -m omnistat.node_monitoring --configfile={self.configFile}"

        if "OMNISTAT_EXPORTER_COREBINDING" in os.environ:
            corebinding = int(os.getenv("OMNISTAT_EXPORTER_COREBINDING"))
            logging.info(
                "[exporter]: Overriding corebinding setting using OMNISTAT_EXPORTER_COREBINDING=%i" % corebinding
            )

        # Assume environment is the same across nodes; if numactl is present
        # here, we expect it to be present on all nodes.
        numa_command = self.verifyNumaCommand(corebinding)
        if numa_command:
            numa_command_string = " ".join(numa_command)
            cmd = f"{numa_command_string} {cmd}"
        else:
            logging.info("Skipping exporter corebinding")

        if self.__hosts:
            logging.info("[exporter]: Saving RMS job state locally to compute hosts...")
            if self.__rms == "slurm":
                numNodes = os.getenv("SLURM_JOB_NUM_NODES")
                srun_cmd = [
                    "srun",
                    "-N %s" % numNodes,
                    "--ntasks-per-node=1",
                    "%s" % sys.executable,
                    "%s/omnistat-rms-env" % self.binDir,
                    "--nostep",
                    "%s"
                    % self.runtimeConfig["omnistat.collectors.rms"].get("job_detection_file", "/tmp/omni_rmsjobinfo"),
                ]
                utils.runShellCommand(srun_cmd, timeout=35, exit_on_error=True)
            elif self.__rms == "flux":
                flux_cmd = [
                    "flux",
                    "exec",
                    "%s" % sys.executable,
                    "%s/omnistat-rms-env" % self.binDir,
                    "--nostep",
                    "%s"
                    % self.runtimeConfig["omnistat.collectors.rms"].get("job_detection_file", "/tmp/omni_rmsjobinfo"),
                ]
                utils.runShellCommand(flux_cmd, timeout=35, exit_on_error=True)

            logging.info("Launching exporters in parallel via ssh")

            client = ParallelSSHClient(self.__hosts, allow_agent=False, timeout=300, pool_size=350, pkey=ssh_key)
            try:
                output = client.run_command(
                    f"sh -c 'cd {os.getcwd()} && PYTHONPATH={':'.join(sys.path)} {cmd}'", stop_on_errors=False
                )
            except:
                logging.info("Exception thrown launching parallel ssh client")

            # verify exporter available on all nodes...
            if len(self.__hosts) <= 8:
                psecs = 5
            elif len(self.__hosts) <= 128:
                psecs = 30
            else:
                psecs = 90

            logging.info("Exporters launched, pausing for %i secs" % psecs)
            time.sleep(psecs)  # <-- needed for slow SLURM query times on ORNL
            numHosts = len(self.__hosts)
            numAvail = 0

            if True:
                logging.info("Testing exporter availability")
                delay_start = 0.05
                hosts_ok = []
                hosts_bad = []
                for host in self.__hosts:
                    host_ok = False
                    for iter in range(1, 25):
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            result = s.connect_ex((host, int(port)))
                            if result == 0:
                                numAvail = numAvail + 1
                                hosts_ok.append(host)
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
                        hosts_bad.append(host)

                logging.info("%i of %i exporters available" % (numAvail, numHosts))
                if numAvail == numHosts:
                    logging.info("User mode data collectors: SUCCESS")

                # cache any failed hosts to file
                jobid = os.getenv("SLURM_JOB_ID", None)
                if jobid:
                    fileout = "omnistat_failed_hosts.%s.out" % jobid
                    if hosts_bad:
                        with open(fileout, "w") as f:
                            for host in hosts_bad:
                                f.write(host + "\n")
                        f.close()
                        logging.info("Cached failed startup hosts in %s" % fileout)

        return

    def stopExporters(self, victoriaMode=False):
        self.rmsDetection()
        port = self.runtimeConfig["omnistat.collectors"].get("port", "8001")
        for host in self.__hosts:
            logging.info("Stopping exporter for host -> %s" % host)
            cmd = ["curl", f"{host}:{port}/shutdown"]
            logging.debug("-> running command: %s" % cmd)
            timeout = 10
            if victoriaMode:
                timeout = 120
            utils.runShellCommand(cmd, timeout=timeout)
        return

    def verifyNumaCommand(self, coreid):
        """Verify numactl is available and works with supplied core id when provided

        Args:
            coreid (int): desired CPU core to pin with numacl

        Returns:
            list: numactl command
        """

        numactl = shutil.which("numactl")
        if not numactl:
            return None

        if not isinstance(coreid, int):
            return None

        # we have numactl and a core provided - verify we can use it locally
        numa_command = ["numactl", f"--physcpubind={coreid}"]

        results = utils.runShellCommand(numa_command + ["hostname"], timeout=2)
        if results.returncode != 0:
            logging.warning("Unable to use numactl with supplied cpu core = %i" % coreid)
            logging.debug("--> " + results.stdout.splitlines()[0])
            logging.debug("--> " + results.stderr.splitlines()[0])
            return None
        else:
            return numa_command


def main():
    userUtils = UserBasedMonitoring()

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
    parser.add_argument("--configfile", type=str, help="runtime config file", default=None)
    parser.add_argument("--startserver", help="Start local prometheus server", action="store_true")
    parser.add_argument("--stopserver", help="Stop local prometheus server", action="store_true")
    parser.add_argument("--startexporters", help="Start data exporters", action="store_true")
    parser.add_argument("--stopexporters", help="Stop data exporters", action="store_true")
    parser.add_argument("--start", help="Start all necessary user-based monitoring services", action="store_true")
    parser.add_argument("--stop", help="Stop all user-based monitoring services", action="store_true")
    parser.add_argument("--interval", type=float, help="Monitoring sampling interval in secs (default=30)")
    parser.add_argument(
        "--push",
        help="Initiate data collection in push mode with VictoriaMetrics",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    userUtils.setup(args.configfile)
    if args.interval:
        userUtils.setMonitoringInterval(args.interval)

    victoriaMode = args.push

    if args.startserver:
        userUtils.startPromServer(victoriaMode=victoriaMode)
    elif args.stopserver:
        userUtils.stopPromServer(victoriaMode=victoriaMode)
    elif args.startexporters:
        userUtils.startExporters(victoriaMode=victoriaMode)
    elif args.stopexporters:
        userUtils.stopExporters(victoriaMode=victoriaMode)
    elif args.start:
        if victoriaMode:
            logging.info("Initiating data collection in [push] mode -> VictoriaMetrics")
        else:
            logging.info("Initiating data collection in [pull] mode -> Prometheus")
        userUtils.startPromServer(victoriaMode=victoriaMode)
        userUtils.startExporters(victoriaMode=victoriaMode)
    elif args.stop:
        userUtils.stopExporters(victoriaMode=victoriaMode)
        userUtils.stopPromServer(victoriaMode=victoriaMode)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
