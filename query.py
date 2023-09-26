from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
import sys
import numpy as np
import subprocess
import argparse

# define local site configuration
config= {}
config["mi1004x"]     = {"num_gpus":4}
config["mi1008x"]     = {"num_gpus":8}
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

# require jobID as input
parser = argparse.ArgumentParser()
parser.add_argument('--job',help='jobId to query',required=True)

args = parser.parse_args()
jobID = int(args.job)

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

# print(query)
# results = prometheus.custom_query_range(query=query,start_time=start_time,end_time = end_time,step=60)
#results = prometheus.custom_query(query=query)
#results = prometheus.custom_query_range('card0_rocm_utilization * on (instance) slurmjob_info{jobid="%s"}',start_time,end_time,step=60)
results = prometheus.custom_query_range("card0_rocm_utilization * on (instance) slurmjob_info{jobid=\"%s\"}" % jobID,start_time,end_time,step=60)
# #results = prometheus.custom_query("card0_rocm_utilization")
# print(results)
# sys.exit(1)

# Detect hosts associated with this job
hosts = []
for result in results:
    hosts.append(result['metric']['instance'])

print("# of active hosts = %i" % len(hosts) )
print(hosts)
#

statistics = {}
numGpus = config[jobinfo['partition']]['num_gpus']
print(numGpus)

# Query metrics from assigned hosts during the job begin/end start period
#for metric in ["card0_rocm_utilization","card1_rocm_utilization","card2_rocm_utilization","card3_rocm_utilization",
#                "card4_rocm_utilization","card5_rocm_utilization","card6_rocm_utilization","card7_rocm_utilization"]:
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


## # Memory utilization
## for gpu in range(numGpus):
##     metric_used  = "card" + str(gpu) + "_rocm_vram_used"
##     metric_total = "card" + str(gpu) + "_rocm_vram_total"
## 
##     for host in hosts:
##         results = prometheus.custom_query_range("max(%s * on (instance) slurmjob_info{jobid=\"%s\"})" %
##                                                 (metric_used,jobid,),start_time,end_time,step=60)
## 
##         print(results)
##         sys.exit(1)
##         assert(len(results) == 1)
##         data = results[0]['values']
##         # print(data)
##         # sys.exit(1)
##         # print("%s %s %s (%i)" % (host,datetime.fromtimestamp(data[0][0]),datetime.fromtimestamp(data[-1][0]),
##         #     len(data)))
## 
##         # compute relevant statistics
##         data2 = np.asarray(data,dtype=float)
##         statistics[memory + "_max"]  = np.max(data2[:,1])
## ##         statistics[metric + "_min"]  = np.min(data2[:,1])
## ##         statistics[metric + "_mean"] = np.mean(data2[:,1])
## ##         statistics[metric + "_std"]  = np.std(data2[:,1])        

# summarize statistics

system = "HPC Fund"

print(" ")
print(" ")
print("HPC Report Card for Job # %i" % jobID)
print(" ")
print("Job Overview (Num Nodes = %i, Machine = %s)" % (len(hosts),system))
print(" --> Start time = %s" % start_time)
print(" --> End   time = %s" % end_time.strftime("%Y-%m-%d %H:%M:%S"))
print("")
print("--> GPU Core Utilization")
print("   | GPU # | Min (%) | Max (%) | Mean (%)|")
for card in range(numGpus):
    key = "card" + str(card) + "_rocm_utilization"
    print("   |%6s |%7.1f  |%7.1f  |%7.1f  |" % (card,statistics[key+"_min"],statistics[key+"_max"],statistics[key+"_mean"]))
