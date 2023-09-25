from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
import sys
import numpy as np
import subprocess

# define local site configuration
config= {}
config["mi1004x"]     = {"num_gpus":4}
config["mi1008x"]     = {"num_gpus":8}
config["system_name"] = "HPC Fund"

def query_slurm_job(id):
    cmd = ["sacct","-n","-P","-X","-j",id,"--format","Start,End,NNodes,Partition"]
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

#prometheus_url = "http://10.0.100.11:9090"
prometheus = PrometheusConnect(url="http://10.0.100.11:9090")

# Define the query
#query = 'up == 1'
jobID=11973
query = 'slurmjob_jobid==11962'
query = 'slurmjob_info{jobid="12263"}'
#query = 'slurmjob_jobid'

jobid = "12263"
jobid = "12271"
jobid = "12304"
jobid = "12318"
jobinfo = query_slurm_job(jobid)

# now = datetime.now().replace(minute=0,second=0,microsecond=0)
# start_time = now - timedelta(days=4)
#now = datetime.now().strftime('%Y-%m-%d %H:%M:00')
# formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')

# start_time = datetime.strptime("2023-09-11T16:57:52",'%Y-%m-%dT%H:%M:%S')
# end_time   = datetime.strptime("2023-09-11T17:27:46",'%Y-%m-%dT%H:%M:%S')

# start_time = datetime.strptime("2023-09-11T17:51:05",'%Y-%m-%dT%H:%M:%S')
# end_time   = datetime.strptime("2023-09-12T17:51:31",'%Y-%m-%dT%H:%M:%S')


start_time = datetime.strptime("2023-09-15T17:51:05",'%Y-%m-%dT%H:%M:%S')
end_time   = datetime.strptime("2023-09-20T17:51:31",'%Y-%m-%dT%H:%M:%S')




start_time = datetime.strptime(jobinfo['begin_date'],'%Y-%m-%dT%H:%M:%S')
if jobinfo['end_date'] == "Unknown":
    end_time   = datetime.now()
else:   
    end_time   = datetime.strptime(jobinfo['end_date'],  '%Y-%m-%dT%H:%M:%S')

## print("job = %s" % jobid)
## print("--> start time = %s" % start_time)
## print("--> end   time = %s" % end_time)
#sys.exit(1)

# print(now)
# print(start_time)
# print(end_time)
# sys.exit(1)

# print(query)
# results = prometheus.custom_query_range(query=query,start_time=start_time,end_time = end_time,step=60)
#results = prometheus.custom_query(query=query)
#results = prometheus.custom_query_range('card0_rocm_utilization * on (instance) slurmjob_info{jobid="%s"}',start_time,end_time,step=60)
results = prometheus.custom_query_range("card0_rocm_utilization * on (instance) slurmjob_info{jobid=\"%s\"}" % jobid,start_time,end_time,step=60)
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
        results = prometheus.custom_query_range("avg(%s * on (instance) slurmjob_info{jobid=\"%s\"})" % (metric,jobid),start_time,end_time,step=60)

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

# summarize statistics

system = "HPC Fund"

print(" ")
print(" ")
print("HPC Report Card for Job # %i" % jobID)
print(" ")
print("Job Overview (Num Nodes = %i, Machine = %s)" % (len(hosts),system))
print(" --> Start time = %s" % start_time)
print(" --> End   time = %s" % end_time)
print("")
print("--> GPU Core Utilization")
print("   | GPU # | Min (%) | Max (%) | Mean (%)|")
for card in range(numGpus):
    key = "card" + str(card) + "_rocm_utilization"
    print("   |%6s |%7.1f  |%7.1f  |%7.1f  |" % (card,statistics[key+"_min"],statistics[key+"_max"],statistics[key+"_mean"]))
