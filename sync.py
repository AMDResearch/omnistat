#!/usr/bin/env python3

import argparse
import datetime
import utils
import time
import signal
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--interval",help="Monitoring sampling interval in secs (default=60)",default=60,type=int)
args = parser.parse_args()

interval = args.interval

print("Setting up to query at %i (sec) interval" % interval)

now = datetime.datetime.today() + datetime.timedelta(seconds=2)
print(now)

def query_smi():
    results = utils.runShellCommand(["/opt/rocm-5.7.1/bin/rocm-smi","-P","-c","-u","-f","-t","--showmeminfo","vram","--json"])
    #print(results.stdout)
    #print(" ")

def stop_execution(sig, frame):
    print("Received SIGUSR2 signal...terminating")
    sys.exit(0)

# register signal for termination
signal.signal(signal.SIGUSR2, stop_execution)

for i in range(0,1000):
    t1 = time.time()
    print(datetime.datetime.today())
    query_smi()
    delta = time.time() - t1
    #print("query time = %f" % (delta))
    #print("additional sleep = %f" % (interval - delta))
    time.sleep(interval - delta)

