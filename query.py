#!/usr/bin/env python3

from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
import sys
import os
import numpy as np
import subprocess
import argparse

# define local site configuration
config= {}
config["mi1004x"]     = {"num_gpus":4}
config["mi1008x"]     = {"num_gpus":8}
config["ci"]          = {"num_gpus":4}
config["system_name"] = "HPC Fund"

def query_slurm_job(id):
    cmd = ["sacct","-n","-P","-X","-j",str(id),"--format","Start,End,NNodes,Partition"]
    results = subprocess.check_output(cmd,universal_newlines=True).strip()
    results = results.split("\n")
    assert(len(results)==1)

    jobdata = {}
    data = results[0].split("|")
    jobdata["begin_date"] = data[0]
    jobdata["end_date"]   = data[1]
    jobdata["num_nodes"]  = data[2]
    jobdata["partition"]  = data[3]

    return jobdata

# command line args (jobID is required)
parser = argparse.ArgumentParser()
parser.add_argument('--job',help='jobId to query',required=True)
parser.add_argument('--output',help='location for stdout report')

args = parser.parse_args()
jobID = int(args.job)

outputFile = sys.stdout
if args.output:
    outputFile = args.output
    if not os.path.isfile(outputFile):
        sys.exit()

#prometheus_url = "http://10.0.100.11:9090"
prometheus = PrometheusConnect(url="http://10.0.100.11:9090")

# query jobinfo
assert(jobID > 1)
jobinfo = query_slurm_job(jobID)

start_time = datetime.strptime(jobinfo['begin_date'],'%Y-%m-%dT%H:%M:%S')
if jobinfo['end_date'] == "Unknown":
    end_time   = datetime.now()
else:   
    end_time   = datetime.strptime(jobinfo['end_date'],  '%Y-%m-%dT%H:%M:%S')

# Detect hosts associated with this job
hosts = []
results = prometheus.custom_query_range("card0_rocm_utilization * on (instance) slurmjob_info{jobid=\"%s\"}" % jobID,start_time,end_time,step=60)
for result in results:
    hosts.append(result['metric']['instance'])

#print("# of active hosts = %i" % len(hosts) )
#print(hosts)

statistics = {}
numGpus = 0

if jobinfo['partition'] in config:
    if 'num_gpus' in config[jobinfo['partition']]:
        numGpus = config[jobinfo['partition']]['num_gpus']

# Query GPU utilization metrics from assigned hosts during the job begin/end start period
for gpu in range(numGpus):
    metric = "card" + str(gpu) + "_rocm_utilization"

    for host in hosts:
        # print(metric)
        results = prometheus.custom_query_range("avg(%s * on (instance) slurmjob_info{jobid=\"%s\"})" % (metric,jobID),start_time,end_time,step=60)

        # if metric == "card1_rocm_utilization":
        #     mydata = results[0]['values']
        #     for item in mydata:
        #         print("%s %s" % (datetime.fromtimestamp(item[0]),item[1]))
        #     sys.exit(1)

        assert(len(results) == 1)
        data = results[0]['values']
        # print(data)
        # sys.exit(1)
        # print("%s %s %s (%i)" % (host,datetime.fromtimestamp(data[0][0]),datetime.fromtimestamp(data[-1][0]),
        #     len(data)))

        # compute relevant statistics
        data2 = np.asarray(data,dtype=float)
        statistics[metric + "_max"]  = np.max(data2[:,1])
        statistics[metric + "_min"]  = np.min(data2[:,1])
        statistics[metric + "_mean"] = np.mean(data2[:,1])
        statistics[metric + "_std"]  = np.std(data2[:,1])
 
        # verify mean
        # myavg = 0.0
        # for result in results[0]['values']:
        #     print(datetime.fromtimestamp(result[0]),result[1])
        #     myavg = myavg + float(result[1])
        # myavg = myavg / len(results[0]['values'])
        # print(myavg)


# Memory utilization
gpu_memory_avail = None

for gpu in range(numGpus):
    
    # Get total GPU memory - we assume it is the same on all assigned GPUs
    metric = "card" + str(gpu) + "_rocm_vram_total"
    results = prometheus.custom_query("max(%s * on (instance) slurmjob_info{jobid=\"%s\"})" %
                                                (metric,jobID))

    if not gpu_memory_avail:
        gpu_memory_avail = int(results[0]['value'][1])
        assert(gpu_memory_avail > 1024*1024*1024)
    else:
        assert(int(results[0]['value'][1]) == gpu_memory_avail)

    # query used gpu memory
    metric_used  = "card" + str(gpu) + "_rocm_vram_used"
    for host in hosts:
        results = prometheus.custom_query_range("max(%s * on (instance) slurmjob_info{jobid=\"%s\"})" %
                                                (metric_used,jobID),start_time,end_time,step=60)
        assert(len(results) == 1)
        data = results[0]['values']
        # compute relevant statistics
        data2 = np.asarray(data,dtype=int)
        statistics[metric_used + "_max"]  = np.max(100.0 * data2[:,1] / gpu_memory_avail)
        statistics[metric_used + "_mean"] = np.mean(100.0 * data2[:,1] / gpu_memory_avail)


# summarize statistics

system = "HPC Fund"

if args.output:
    output = open(outputFile,"a")
    sys.stdout = output

print("")
print("-" * 40)
print("HPC Report Card for Job # %i" % jobID)
print("-" * 40)
print("")
print("Job Overview (Num Nodes = %i, Machine = %s)" % (len(hosts),system))
print(" --> Start time = %s" % start_time)
print(" --> End   time = %s" % end_time.strftime("%Y-%m-%d %H:%M:%S"))
print("")
print("--> GPU Core Utilization")
print("   | GPU # |  Max (%) | Mean (%)|")
for card in range(numGpus):
    key = "card" + str(card) + "_rocm_utilization"
    print("   |%6s |%8.1f  |%7.1f  |" % (card,statistics[key+"_max"],statistics[key+"_mean"]))

print("")
print("--> GPU Memory Utilization")
print("   | GPU # |  Max (%) | Mean (%)|")
for card in range(numGpus):
    key = "card" + str(card) + "_rocm_vram_used"
    print("   |%6s |%8.2f  |%7.2f  |" % (card,statistics[key+"_max"],statistics[key+"_mean"]))

if args.output:
    output.close