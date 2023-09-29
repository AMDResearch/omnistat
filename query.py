#!/usr/bin/env python3

from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
import sys
import os
import numpy as np
import subprocess
import argparse


class queryMetrics:

    def set_options(self,jobID=None,output_file=None,pdf=None):
        if jobID:
            self.jobID=int(jobID)
        if output_file:
            self.outputFile = output_file
        if pdf:
            self.pdf = pdf
        return

    def __init__(self):
        self.config = {}
        self.config["mi1004x"] = {"num_gpus": 4}
        self.config["mi1008x"] = {"num_gpus": 8}
        self.config["ci"] = {"num_gpus": 4}
        self.config["system_name"] = "HPC Fund"
        self.config["prometheus_url"] = "http://10.0.100.11:9090"

        self.jobID = None
        self.enable_redirect = False
        self.output_file = None
        self.pdf = None

        # # input options
        # self.jobID = None
        # self.redirect_output = False
        # self.enable_PDF = False

        # # (optionally) redirect stdout
        # #outputFile = sys.stdout
        # self.redirect = redirect_output
        # if self.redirect:
        #     outputFile = args.output
        #     if not os.path.isfile(outputFile):
        #         sys.exit()
        #     else:
        #         self.output = open(outputFile,"a")
        #         sys.stdout = self.output
        #         self.redirect = True

    # def __init(self,jobID=None):
    #     self.jobID = jobID
    #     self.init_config()
        
    #     self.initiallize()
    #     return
    
    # def __init__(self):

    #     # command line args (jobID is required)
    #     parser = argparse.ArgumentParser()
    #     parser.add_argument("--job", help="jobId to query", required=True)
    #     parser.add_argument("--output", help="location for stdout report")
    #     parser.add_argument("--pdf", help="generate PDF report")

    #     args = parser.parse_args()
    #     self.jobID = int(args.job)
    #     if args.output
        

    # define local site configuration
    def setup(self):
        # self.config = {}
        # self.config["mi1004x"] = {"num_gpus": 4}
        # self.config["mi1008x"] = {"num_gpus": 8}
        # self.config["ci"] = {"num_gpus": 4}
        # self.config["system_name"] = "HPC Fund"
        # self.config["prometheus_url"] = "http://10.0.100.11:9090"


        # args = parser.parse_args()
        # self.jobID = int(args.job)

        # (optionally) redirect stdout
        # outputFile = sys.stdout
        # self.redirect = False
        if self.output_file:
            #outputFile = self.output_file
            if not os.path.isfile(self.output_file):
                sys.exit()
            else:
                self.output = open(self.output_file,"a")
                sys.stdout = self.output
                self.enable_redirect = True

        self.prometheus = PrometheusConnect(url=self.config["prometheus_url"])

        # query jobinfo
        assert self.jobID > 1
        self.jobinfo = self.query_slurm_job()

        self.start_time = datetime.strptime(
            self.jobinfo["begin_date"], "%Y-%m-%dT%H:%M:%S"
        )
        if self.jobinfo["end_date"] == "Unknown":
            self.end_time = datetime.now()
        else:
            self.end_time = datetime.strptime(
                self.jobinfo["end_date"], "%Y-%m-%dT%H:%M:%S"
            )

        # NOOP if job is very short running
        runtime = (self.end_time - self.start_time).total_seconds()
        if runtime < 61:
            sys.exit()

        self.get_hosts()

    # gather relevant job data from resource manager
    def query_slurm_job(self):
        id = self.jobID
        cmd = [
            "sacct",
            "-n",
            "-P",
            "-X",
            "-j",
            str(id),
            "--format",
            "Start,End,NNodes,Partition",
        ]
        results = subprocess.check_output(cmd, universal_newlines=True).strip()
        results = results.split("\n")
        assert len(results) == 1

        jobdata = {}
        data = results[0].split("|")
        jobdata["begin_date"] = data[0]
        jobdata["end_date"] = data[1]
        jobdata["num_nodes"] = data[2]
        jobdata["partition"] = data[3]

        return jobdata

    # Detect hosts associated with this job
    def get_hosts(self):
        self.hosts = []
        results = self.prometheus.custom_query_range(
            'card0_rocm_utilization * on (instance) slurmjob_info{jobid="%s"}'
            % self.jobID,
            self.start_time,
            self.end_time,
            step=60,
        )
        for result in results:
            self.hosts.append(result["metric"]["instance"])

    def generate_report_card(self):
        system = "HPC Fund"

        statistics = {}
        numGpus = 0

        if self.jobinfo["partition"] in self.config:
            if "num_gpus" in self.config[self.jobinfo["partition"]]:
                numGpus = self.config[self.jobinfo["partition"]]["num_gpus"]

        # # Query GPU utilization metrics from assigned hosts during the job begin/end start period
        for gpu in range(numGpus):
            metric = "card" + str(gpu) + "_rocm_utilization"

            for host in self.hosts:
                results = self.prometheus.custom_query_range(
                    'avg(%s * on (instance) slurmjob_info{jobid="%s"})'
                    % (metric, self.jobID),
                    self.start_time,
                    self.end_time,
                    step=60,
                )

                assert len(results) == 1
                data = results[0]["values"]

                # compute relevant statistics
                data2 = np.asarray(data, dtype=float)
                statistics[metric + "_max"] = np.max(data2[:, 1])
                statistics[metric + "_min"] = np.min(data2[:, 1])
                statistics[metric + "_mean"] = np.mean(data2[:, 1])
                statistics[metric + "_std"] = np.std(data2[:, 1])

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
            results = self.prometheus.custom_query_range(
                'max(%s * on (instance) slurmjob_info{jobid="%s"})'
                % (metric, self.jobID),self.start_time,self.end_time,step=60
            )

            if not gpu_memory_avail:
                gpu_memory_avail = int(results[0]["values"][0][1])
                assert gpu_memory_avail > 1024 * 1024 * 1024
            else:
                assert int(results[0]["values"][0][1]) == gpu_memory_avail

            # query used gpu memory
            metric_used = "card" + str(gpu) + "_rocm_vram_used"
            for host in self.hosts:
                results = self.prometheus.custom_query_range(
                    'max(%s * on (instance) slurmjob_info{jobid="%s"})'
                    % (metric_used, self.jobID),
                    self.start_time,
                    self.end_time,
                    step=60,
                )
                assert len(results) == 1
                data = results[0]["values"]
                # compute relevant statistics
                data2 = np.asarray(data, dtype=int)
                statistics[metric_used + "_max"] = np.max(
                    100.0 * data2[:, 1] / gpu_memory_avail
                )
                statistics[metric_used + "_mean"] = np.mean(
                    100.0 * data2[:, 1] / gpu_memory_avail
                )

        # summarize statistics
        print("")
        print("-" * 40)
        print("HPC Report Card for Job # %i" % self.jobID)
        print("-" * 40)
        print("")
        print("Job Overview (Num Nodes = %i, Machine = %s)" % (len(self.hosts), system))
        print(" --> Start time = %s" % self.start_time)
        print(" --> End   time = %s" % self.end_time.strftime("%Y-%m-%d %H:%M:%S"))
        print("")
        print("--> GPU Core Utilization")
        print("   | GPU # |  Max (%) | Mean (%)|")
        for card in range(numGpus):
            key = "card" + str(card) + "_rocm_utilization"
            print(
                "   |%6s |%8.1f  |%7.1f  |"
                % (card, statistics[key + "_max"], statistics[key + "_mean"])
            )
        print("")
        print("--> GPU Memory Utilization")
        print("   | GPU # |  Max (%) | Mean (%)|")
        for card in range(numGpus):
            key = "card" + str(card) + "_rocm_vram_used"
            print(
                "   |%6s |%8.2f  |%7.2f  |"
                % (card, statistics[key + "_max"], statistics[key + "_mean"])
            )

    def __del__(self):
        if self.enable_redirect:
            self.output.close()

def main():

    # command line args (jobID is required)
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="jobId to query", required=True)
    parser.add_argument("--output", help="location for stdout report")
    parser.add_argument("--pdf", help="generate PDF report")
    args = parser.parse_args()

    # print(args.output,args.pdf)

    query = queryMetrics()
    query.set_options(jobID=args.job,output_file=args.output,pdf=args.pdf)
    query.setup()
    query.generate_report_card()

if __name__ == "__main__":
    main()
