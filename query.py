from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
import sys
import numpy as np

#prometheus_url = "http://10.0.100.11:9090"
prometheus = PrometheusConnect(url="http://10.0.100.11:9090")

# Define the query
#query = 'up == 1'
jobID=11973
query = 'slurmjob_jobid==11962'
query = 'slurmjob_jobid==11973'
#query = 'slurmjob_jobid'

# Query Prometheus for the time series data
#results = prometheus.custom_query(query=query)
#results = prometheus.custom_query(query=query, params={'step':'5m'})
#results = prometheus.custom_query(query=query, params={'time': '5m'})

now = datetime.now().replace(minute=0,second=0,microsecond=0)
start_time = now - timedelta(days=4)
#now = datetime.now().strftime('%Y-%m-%d %H:%M:00')
# formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')

start_time = datetime.strptime("2023-09-11T16:57:52",'%Y-%m-%dT%H:%M:%S')
end_time   = datetime.strptime("2023-09-11T17:27:46",'%Y-%m-%dT%H:%M:%S')

start_time = datetime.strptime("2023-09-11T17:51:05",'%Y-%m-%dT%H:%M:%S')
end_time   = datetime.strptime("2023-09-12T17:51:31",'%Y-%m-%dT%H:%M:%S')

# print(now)
# print(start_time)
# print(end_time)
#print(formatted_time)
#sys.exit(1)

results = prometheus.custom_query_range(query=query,start_time=start_time,end_time = end_time,step=60)

# Detect hosts associated with this job
hosts = []
for result in results:
    hosts.append(result['metric']['instance'])

# print("# of active hosts = %i" % len(hosts) )
# print(hosts)

statistics = {}

# Query metrics from assigned hosts during the job begin/end start period
for metric in ["card0_rocm_utilization","card1_rocm_utilization","card2_rocm_utilization","card3_rocm_utilization",
                "card4_rocm_utilization","card5_rocm_utilization","card6_rocm_utilization","card7_rocm_utilization"]:
    for host in hosts:
        query='avg(card0_rocm_utilization{instance="t004-008:8000"})'
        #query=metric + "{instance=\"" + host + "\"}"
        #query_avg = avg
        #print(query)
        #results = prometheus.custom_query_range(query=query,start_time=start_time,end_time = end_time,step=60)
        results= prometheus.get_metric_range_data(metric,start_time=start_time,end_time=end_time,
        label_config={'instance':'t004-008:8000'})
        # df = MetricSnapshotDataFrame(results)
        # print(results)
        # print(len(results))
        #print(results)
        #print(len(results))
        assert(len(results) == 1)
        data = results[0]['values']
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

numGpus = 8
# numNodes = 1
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
print("   | GPU # | Min (%) | Max (%) | Mean (%) |")
for card in range(numGpus):
    key = "card" + str(card) + "_rocm_utilization"
    print("   |%6s |%7.1f  |%7.1f  |%7.1f  |" % (card,statistics[key+"_min"],statistics[key+"_max"],statistics[key+"_mean"]))



# # Find min/max times and instance names
# for result in results:
#     # metric_name = result['metric']['__name__']
#     # instance = result['metric'].get('instance', '')
#     # value = result['value'][1]

#     # print(f"Metric: {metric_name}, Instance: {instance}, Value: {value}")
#     # print(result['metric'])
#     # print(type(result))
#     # print(type(result['values']))
# #    print(result)
#     # sys.exit(1)
#     minTime = result['values'][0][0]
#     maxTime = result['values'][-1][0]
#     numPoints = len(result['values'])
# #    print(numPoints)
#     print("Instance = %s Min time = %s Max time = %s (%s points)" % (result['metric']['instance'],
#             datetime.fromtimestamp(minTime),datetime.fromtimestamp(maxTime),numPoints))
# #    for value in result['values']:
# #        print(value[0],value[1])
#         # print(datetime.fromtimestamp(value[0]),value[1])
# #    sys.exit(1)

# print(results[0])
# print(results[1])