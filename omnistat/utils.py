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

import configparser
import importlib.resources
import logging
import os
import shutil
import subprocess
import sys

from importlib.metadata import version
from pathlib import Path


def convert_bdf_to_gpuid(bdf_string):
    """
    Converts BDF text string in hex format to a GPU location id in the form written by kfd driver
    into /sys/class/kfd/kfd/topology/nodes/<node>/properties

    Args:
        bdf_string (string): bdf string for GPU (domain:bus:device.func)

    Returns:
        int: location_id
    """

    domain = int(bdf_string.split(":")[0], 16)
    # strip leading domain
    bdf = bdf_string.split(":")[1:]
    # cull out bus, device, and function as ints
    bus = int(bdf[0], 16)
    dev_func = bdf[1].split(".")
    device = int(dev_func[0], 16)
    function = int(dev_func[1], 16)
    # assemble id per kfd driver
    location_id = (bus << 8) | function
    return location_id


def pass_through_indexing(numGpus):
    """returns a pass through GPU indexingwith 0:0, 1:1, etc.  Intended for use in cases where
    exact mapping cannot be ascertained by reading sysfs topology files.
    """
    gpu_index_mapping = {}
    for i in range(numGpus):
        gpu_index_mapping[i] = str(i)
    return gpu_index_mapping


def gpu_index_mapping_based_on_guids(guidMapping, expectedNumGPUs):
    """Generate a mapping between kfd gpu_id  (SMI lib) to those of HIP_VISIBLE_DEVICES. Intended for
    use with metric labeling to identify devices based on HIP_VISIBLE_DEVICES indexing.

    Args:
        guidMapping (dict): maps kfd indices to gpu_ids
        expectedNumGPUs (int): number of GPUs detected locally

    Returns:
        dict: maps kfd indices to HIP_VISIBLE_DEVICES indices
    """
    kfd_nodes = "/sys/class/kfd/kfd/topology/nodes"
    logging.info("GPU topology indexing: Scanning devices from %s" % kfd_nodes)
    if not os.path.isdir(kfd_nodes):
        logging.warn("--> directory not found")
        return pass_through_indexing(expectedNumGPUs)

    devices = os.listdir(kfd_nodes)
    numNonGPUs = 0
    numGPUs = 0
    tmpMapping = {}
    for id in range(len(devices)):
        file = os.path.join(kfd_nodes, str(id), "gpu_id")
        logging.debug("--> reading contents of %s" % file)
        if os.path.isfile(file):
            with open(file) as f:
                guid = int(f.readline().strip())
            if guid == 0:
                numNonGPUs += 1
                logging.debug("--> ...ignoring CPU device")
            else:
                tmpMapping[guid] = numGPUs
                numGPUs += 1
        else:
            logging.warn("Unable to access expected file (%s)" % file)
            return pass_through_indexing(expectedNumGPUs)

    if numGPUs != expectedNumGPUs:
        logging.warn("--> did not detect expected number of GPUs in sysfs (%i vs %i)" % (numGPUs, expectedNumGPUs))
        return pass_through_indexing(expectedNumGPUs)

    gpuMappingOrder = {}

    for gpuIndex, id in guidMapping.items():
        if id in tmpMapping:
            gpuMappingOrder[gpuIndex] = str(tmpMapping[id])
        else:
            logging.warn("--> unable to resolve gpu location_id=%s" % id)
            return pass_through_indexing(expectedNumGPUs)

    logging.info("--> Mapping: %s" % gpuMappingOrder)
    return gpuMappingOrder


def gpu_index_mapping_based_on_bdfs(bdfMapping, expectedNumGPUs):
    """Generate a mapping between kfd gpu indexing (SMI lib) to those of HIP_VISIBLE_DEVICES. Intended for
    use with metric labeling to identify devices based on HIP_VISIBLE_DEVICES indexing.

    Args:
        bdfMapping (dict): maps kfd indices to location ids derived from bdf strings
        expectedNumGPUs (int): number of GPUs detected locally

    Returns:
        dict: maps kfd indices to HIP_VISIBLE_DEVICES indices
    """
    kfd_nodes = "/sys/class/kfd/kfd/topology/nodes"
    logging.info("GPU topology indexing: Scanning devices from %s" % kfd_nodes)
    if not os.path.isdir(kfd_nodes):
        logging.warn("--> directory not found")
        return pass_through_indexing(expectedNumGPUs)

    devices = os.listdir(kfd_nodes)
    numNonGPUs = 0
    numGPUs = 0
    tmpMapping = {}
    for id in range(len(devices)):
        file = os.path.join(kfd_nodes, str(id), "properties")
        logging.debug("--> reading contents of %s" % file)
        if os.path.isfile(file):
            properties = {}
            with open(file) as f:
                for line in f:
                    key, value = line.strip().split(" ")
                    if key == "location_id":
                        location_id = int(value)
            if location_id == 0:
                numNonGPUs += 1
                logging.debug("--> ...ignoring CPU device")
            else:
                tmpMapping[location_id] = numGPUs
                numGPUs += 1
        else:
            logging.warn("Unable to access expected file (%s)" % file)
            return pass_through_indexing(expectedNumGPUs)

    if numGPUs != expectedNumGPUs:
        logging.warn("--> did not detect expected number of GPUs in sysfs (%i vs %i)" % (numGPUs, expectedNumGPUs))
        return pass_through_indexing(expectedNumGPUs)

    gpuMappingOrder = {}
    for gpuIndex, id in bdfMapping.items():
        if id in tmpMapping:
            gpuMappingOrder[gpuIndex] = str(tmpMapping[id])
        else:
            logging.warn("--> unable to resolve gpu location_id=%s" % id)
            return pass_through_indexing(expectedNumGPUs)

    logging.info("--> Mapping: %s" % gpuMappingOrder)
    return gpuMappingOrder


def error(message):
    """Log an error message and exit

    Args:
        message (string): message
    """
    logging.error("Error: " + message)
    sys.exit(1)


def findConfigFile(configFileArgument=None):
    """Identify configuration file location

    Try to find one of the following locations in the filesystem:
     1. File pointed by configFileArgument (if defined)
     2. File pointed by OMNISTAT_CONFIG (if defined)
     3. Default configuration file in the package

    Args:
        configFileArgument (string, optional): optional path to config file
          provided as argument in the CLI

    Returns:
        string: path to an existing configuration file
    """
    # Resolve path to default config file in the current installation.
    # This configuration is only meant to provide sane defaults to run
    # locally, but most installations will need a custom file.
    packageDir = importlib.resources.files("omnistat")
    configFile = packageDir.joinpath("config/omnistat.default")

    if "OMNISTAT_CONFIG" in os.environ:
        configFile = os.environ["OMNISTAT_CONFIG"]

    if configFileArgument != None:
        configFile = configFileArgument

    if not os.path.isfile(configFile):
        error(f"Unable to find configuration file {configFile}")

    return configFile


def readConfig(configFile):
    """Read and parse configuration file

    Args:
        configFile (string): path to config file

    Returns:
        ConfigParser: object containing configuration options
    """
    print(f"Reading configuration from {configFile}")
    config = configparser.ConfigParser()
    config.read(configFile)
    return config


def runShellCommand(command, capture_output=True, text=True, exit_on_error=False, timeout=1.0):
    """Runs a provided shell command

    Args:
        command (list): shell command with options to execute
        capture_output (bool, optional): _description_. Defaults to True.
        text (bool, optional): _description_. Defaults to True.
        exit_on_error (bool, optional): Whether to exit on error or not. Defaults to False.
    """

    logging.debug("Command to run = %s" % command)
    try:
        results = subprocess.run(command, capture_output=capture_output, text=text, timeout=timeout)
    except subprocess.TimeoutExpired:
        logging.error("ERROR: Process timed out, ran for more than %i sec(s)" % timeout)
        logging.error("       %s" % command)
        if not exit_on_error:
            return None

    if exit_on_error and results.returncode != 0:
        logging.error("ERROR: Command failed")
        logging.error("       %s" % command)
        logging.error("stdout: %s" % results.stdout)
        logging.error("stderr: %s" % results.stderr)
        sys.exit(1)
    return results


def runBGProcess(command, outputFile=".bgcommand.output", mode="w"):
    logging.debug("Command to run in background = %s" % command)
    # results = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=open(outputFile,"w"))

    outfile = open(outputFile, mode)
    results = subprocess.Popen(command, stdout=outfile, stderr=outfile)
    return results


def resolvePath(desiredCommand, envVar):
    """Resolve underlying path to a desired shell command.

    Args:
        desiredCommand (string): desired shell command to resolve
        envVar (string): environment variable string that can optionally provide path to desired command

    Returns:
        string: resolved path to desired comman
    """
    path = None
    command = desiredCommand
    if envVar in os.environ:
        customPath = os.getenv(envVar)
        logging.debug("Overriding command search path with %s=%s" % (envVar, customPath))
        if os.path.isdir(customPath):
            command = customPath + "/" + desiredCommand
        else:
            error("provided %s does not exist -> %s" % (envVar, customPath))
            sys.exit(1)

    # verify we can resolve the desired binary
    path = shutil.which(command)
    if not path:
        logging.error("ERROR: Unable to resolve path for %s" % command)
        return None
    else:
        logging.debug("--> %s path = %s" % (desiredCommand, path))

    return path


def removeQuotes(input):
    """Remove leading/trailing quotes from a string

    Args:
        input (str): string to update
    """
    if input.startswith('"'):
        input = input.strip('"')
    elif input.startswith("'"):
        input = input.strip("'")
    return input


def getVersion():
    """Return omnistat version info"""
    try:
        return version("omnistat")
    except importlib.metadata.PackageNotFoundError:
        # When package is not installed, rely on top-level VERSION file and local git tools to assemble version info

        omnistat_home = Path(__file__).resolve().parent.parent
        versionFile = os.path.join(omnistat_home, "VERSION")
        try:
            with open(versionFile, "r") as file:
                VER = file.read().replace("\n", "")
        except EnvironmentError:
            error("Cannot find VERSION file at {}".format(versionFile))

        # git version query
        SHA = None
        gitDir = os.path.join(omnistat_home, ".git")
        if (shutil.which("git") is not None) and os.path.exists(gitDir):
            gitQuery = subprocess.run(
                ["git", "log", "--pretty=format:%h", "-n", "1"],
                cwd=gitDir,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            if gitQuery.returncode == 0:
                SHA = gitQuery.stdout.decode("utf-8")

        versionInfo = VER
        if SHA:
            versionInfo += " (%s)" % SHA

        return versionInfo


def displayVersion(version):
    """Pretty print versioning info"""
    print("-" * 40)
    print("Omnistat version: %s" % version)
    print("-" * 40)
