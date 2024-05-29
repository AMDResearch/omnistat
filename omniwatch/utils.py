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

import logging
import subprocess
import sys
import os
import shutil

from importlib.metadata import version

from pathlib import Path

def error(message):
    """Log an error message and exit

    Args:
        message (string): message
    """
    logging.error("Error: " + message)
    sys.exit(1)

def runShellCommand(command, capture_output=True, text=True, exit_on_error=False,timeout=1.0):
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

def runBGProcess(command,outputFile=".bgcommand.output",mode='w'):

    logging.debug("Command to run in background = %s" % command)
    #results = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=open(outputFile,"w"))

    outfile = open(outputFile,mode)
    results = subprocess.Popen(command,stdout=outfile,stderr=outfile)
    return results

def resolvePath(desiredCommand,envVar):
    """Resolve underlying path to a desired shell command.

    Args:
        desiredCommand (string): desired shell command to resolve
        envVar (string): environment variable string that can optionally provide path to desired command

    Returns:
        string: resolved path to desired comman
    """
    command = desiredCommand
    if envVar in os.environ:
        customPath = os.getenv(envVar)
        logging.debug("Overriding command search path with %s=%s" % (envVar,customPath))
        if os.path.isdir(customPath):
            command = customPath + "/" + desiredCommand
        else:
            error("provided %s does not exist -> %s" % (envVar,customPath))
            sys.exit(1)

    # verify we can resolve the desired binary
    path = shutil.which(command)
    if not path:
        error("Unable to resolve path for %s" % command)
    else:
        logging.debug("--> %s path = %s" % (desiredCommand,path))

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
    """Return omniwatch version info"""
    return version('omniwatch')


def displayVersion(version):
    """Pretty print versioning info"""
    print("-" * 40)
    print("Omniwatch version: %s" % version)
    print("-" * 40)
