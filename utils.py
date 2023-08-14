import logging
import subprocess
import sys
import os
import shutil

def error(message):
    """Log an error message and exit

    Args:
        message (string): message
    """
    logging.error("Error: " + message)
    sys.exit(1)

def runShellCommand(command, capture_output=True, text=True, exit_on_error=False):
    """Runs a provided shell command

    Args:
        command (list): shell command with options to execute
        capture_output (bool, optional): _description_. Defaults to True.
        text (bool, optional): _description_. Defaults to True.
        exit_on_error (bool, optional): Whether to exit on error or not. Defaults to False.
    """

    logging.debug("Command to run = %s" % command)
    results = subprocess.run(command, capture_output=capture_output, text=text)
    if exit_on_error and results.returncode != 0:
        logging.error("ERROR: Command failed")
        logging.error("       %s" % command)
        logging.error("stdout: %s" % results.stderr)
        logging.error("stderr: %s" % results.stderr)
        sys.exit(1)
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

