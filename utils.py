import logging
import subprocess
import sys

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

def error(message):
    logging.error("Error: " + message)
    sys.exit(1)