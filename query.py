#!/usr/bin/env python3

from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
import sys
import os
import numpy as np
import subprocess
import argparse
import matplotlib.pylab as plt
import matplotlib.dates as mdates
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.units import inch

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

         # local site configuration
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

    def __del__(self):
        if self.enable_redirect:
            self.output.close()

    # complete setup
    def setup(self):

        # (optionally) redirect stdout
        if self.output_file:
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
        self.get_num_gpus()

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


    def get_num_gpus(self):
        self.numGPUs = 0
        if self.jobinfo["partition"] in self.config:
            if "num_gpus" in self.config[self.jobinfo["partition"]]:
                self.numGPUs = self.config[self.jobinfo["partition"]]["num_gpus"]

    def generate_report_card(self):
        system = "HPC Fund"

        statistics = {}
        # numGpus = 0

        # if self.jobinfo["partition"] in self.config:
        #     if "num_gpus" in self.config[self.jobinfo["partition"]]:
        #         numGpus = self.config[self.jobinfo["partition"]]["num_gpus"]

        # Query GPU utilization metrics from assigned hosts during the job begin/end start period
        for gpu in range(self.numGPUs):
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

        for gpu in range(self.numGPUs):
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
        for card in range(self.numGPUs):
            key = "card" + str(card) + "_rocm_utilization"
            print(
                "   |%6s |%8.1f  |%7.1f  |"
                % (card, statistics[key + "_max"], statistics[key + "_mean"])
            )
        print("")
        print("--> GPU Memory Utilization")
        print("   | GPU # |  Max (%) | Mean (%)|")
        for card in range(self.numGPUs):
            key = "card" + str(card) + "_rocm_vram_used"
            print(
                "   |%6s |%8.2f  |%7.2f  |"
                % (card, statistics[key + "_max"], statistics[key + "_mean"])
            )
    def query_time_series_data(self,metric_name,dataType=float):
        results = self.prometheus.custom_query_range(
                    '(%s * on (instance) slurmjob_info{jobid="%s"})'
                    % (metric_name, self.jobID),
                    self.start_time,
                    self.end_time,
                    step=60*1,
                )
        results = np.asarray(results[0]['values'])

        # convert to time format
        time = results[:,0].astype(int).astype('datetime64[s]')
        #time = results[:,0].astype(int)
        # let user decide on conversion type for gauge metric
        if dataType == int:
            values = results[:,1].astype(int)
        elif dataType == float:
            values = results[:,1].astype(float)

        return time,values
    
    def query_gpu_metric(self,metricName):
        stats = {}
        stats['mean'] = []
        stats['max'] = []

        for gpu in range(self.numGPUs):
            metric = "card" + str(gpu) + "_" + metricName

            # Mean results
            results = self.prometheus.custom_query_range(
                'avg(%s * on (instance) slurmjob_info{jobid="%s"})'
                % (metric, self.jobID),
                self.start_time,
                self.end_time,
                step=60,
            )
            
            assert len(results) == 1
            data = results[0]["values"]
            data2 = np.asarray(data, dtype=float)
            stats['mean'].append(np.mean(data2[:,1]))

            # Max results
            results = self.prometheus.custom_query_range(
                'max(%s * on (instance) slurmjob_info{jobid="%s"})'
                % (metric, self.jobID),
                self.start_time,
                self.end_time,
                step=60,
            )

            assert len(results) == 1
            data = results[0]["values"]
            data2 = np.asarray(data, dtype=float)
            stats['max'].append(np.max(data2[:,1]))
            # statistics[metric + "_max"] = np.max(data2[:, 1])
            # statistics[metric + "_min"] = np.min(data2[:, 1])
            # statistics[metric + "_mean"] = np.mean(data2[:, 1])
            # statistics[metric + "_std"] = np.std(data2[:, 1])

        return(stats)
    
    def dumpFile(self,outputFile):
        doc = SimpleDocTemplate(outputFile,pagesize=letter,
                            rightMargin=1 * inch,leftMargin=1 * inch,
                            topMargin=62,bottomMargin=18,showBoundary=0)
        
        styles = getSampleStyleSheet()
        normal = ParagraphStyle('normal')
        Story=[]
        Story.append(Spacer(1,0.1*inch))
        Story.append(HRFlowable(width="100%",thickness=2))
        ptext='''
        <strong>HPC Report Card</strong><br/><br/>
        <strong>JobID</strong>: %s<br/>
        <strong>Start Time</strong>: %s<br/>
        <strong>End Time</strong>: %s<br/>
        ''' % (self.jobID,self.start_time,self.end_time.strftime("%Y-%m-%d %H:%M:%S"))
        Story.append(Paragraph(ptext, styles["Bullet"]))
        Story.append(HRFlowable(width="100%",thickness=2))
        

        # generate Utilization Table
        Story.append(Spacer(1,0.2*inch))
        ptext='''<strong>GPU Core Utilization</strong>'''
        Story.append(Paragraph(ptext,normal))
        Story.append(Spacer(1,0.1*inch))

        stats = self.query_gpu_metric('rocm_utilization')
  
        # print(stats)
        # sys.exit()
        data = []
        data.append(['GPU #','Max (%)','Mean (%)'])

        for gpu in range(self.numGPUs):
            data.append([gpu,"%.1f" % stats['max'][gpu],"%.1f" % stats['mean'][gpu]])

        t=Table(data,rowHeights=[.2*inch] * len(data),
            colWidths=[0.75*inch,0.75*inch])
        t.hAlign='LEFT'
#        t.setStyle(TableStyle([('LINEABOVE',(0,0),(-1,0),1.25,colors.darkgrey)]))
        t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,0),1.5,colors.darkgrey),
                              ('ALIGN',(0,0),(-1,-1),'CENTER')]))
        t.setStyle(TableStyle([('LINEBEFORE',(1,1),(1,-1),1.25,colors.darkgrey),
                               ('LINEAFTER', (2,1),(2,-1),1.25,colors.darkgrey)]))
#         t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.lightgrey)]))
# #                           ('TEXTCOLOR',(0,0),(1,-1),colors.grey)]))

        for each in range(1,len(data)):
            if each % 2 == 0:
                bg_color = colors.lightgrey
            else:
                bg_color = colors.whitesmoke

            t.setStyle(TableStyle([('BACKGROUND', (0, each), (-1, each), bg_color)]))
        Story.append(t)


        Story.append(Spacer(1,0.2*inch))
        Story.append(HRFlowable(width="100%",thickness=1))
        plt.figure(figsize=(9,2.5))

        for gpu in range(self.numGPUs):
            time,util = self.query_time_series_data("card" + str(gpu) + "_rocm_utilization")
            plt.plot(time,util,linewidth=0.4,label='Card %i' % gpu)

        plt.title("GPU Core Utilization")
        plt.legend(bbox_to_anchor =(0.5,-0.27), loc='lower center',
                   ncol=self.numGPUs,frameon=False)
        plt.grid()
        ax = plt.gca()
        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.savefig('utilization1.png',dpi=150,bbox_inches='tight')
        plt.close()
        aplot = Image('utilization1.png')
        aplot.hAlign='LEFT'
        aplot._restrictSize(6.5 * inch, 4 * inch)
        Story.append(aplot)

        # memory utilization
        plt.figure(figsize=(9,2.5))
#        memoryAvail = []
        for gpu in range(self.numGPUs):
            
            time,util = self.query_time_series_data("card" + str(gpu) + "_rocm_vram_total")
            #memoryAvail.append(np.max(util))
            memoryAvail = np.max(util)
            time,util = self.query_time_series_data("card" + str(gpu) + "_rocm_vram_used")
            plt.plot(time,util / memoryAvail,linewidth=0.4,label='Card %i' % gpu)

        plt.axhline(y=100,linestyle='--',color='green')
        plt.title("GPU Memory Used (%)")
        plt.legend(bbox_to_anchor =(0.5,-0.27), loc='lower center',
            ncol=self.numGPUs,frameon=False)
        plt.grid()
        ax = plt.gca()
        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.savefig('utilization2.png',dpi=150,bbox_inches='tight')
        plt.close()
        aplot = Image('utilization2.png')
        aplot.hAlign='LEFT'
        aplot._restrictSize(6.5 * inch, 4 * inch)
        Story.append(aplot)
        

        # temperature utilization
        plt.figure(figsize=(9,2.5))
        for gpu in range(self.numGPUs):
            time,util = self.query_time_series_data("card" + str(gpu) + "_rocm_temp_die_edge")
            plt.plot(time,util,linewidth=0.4,label='Card %i' % gpu)
        plt.title("GPU Temperature - Die Edge (C)")
        plt.legend(bbox_to_anchor =(0.5,-0.27), loc='lower center',
            ncol=self.numGPUs,frameon=False)
        plt.grid()
        ax = plt.gca()
        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.savefig('utilization2.png',dpi=150,bbox_inches='tight')
        plt.close()
        aplot = Image('utilization2.png')
        aplot.hAlign='LEFT'
        aplot._restrictSize(6.5 * inch, 4 * inch)
        Story.append(aplot)

        # clock frequency
        plt.figure(figsize=(9,2.5))
        for gpu in range(self.numGPUs):
            time,util = self.query_time_series_data("card" + str(gpu) + "_rocm_slck_clock_mhz")
            plt.plot(time,util,linewidth=0.4,label='Card %i' % gpu)
        plt.title("GPU Clock Frequency (MHz)")
        plt.legend(bbox_to_anchor =(0.5,-0.27), loc='lower center',
            ncol=self.numGPUs,frameon=False)
        plt.grid()
        ax = plt.gca()
        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.savefig('utilization3.png',dpi=150,bbox_inches='tight')
        plt.close()
        aplot = Image('utilization3.png')
        aplot.hAlign='LEFT'
        aplot._restrictSize(6.5 * inch, 4 * inch)
        Story.append(aplot)

        # power utilization
        plt.figure(figsize=(9,2.5))
        for gpu in range(self.numGPUs):
            time,util = self.query_time_series_data("card" + str(gpu) + "_rocm_avg_pwr")
            plt.plot(time,util,linewidth=0.4,label='Card %i' % gpu)
        plt.title("GPU Average Power (W)")
        plt.legend(bbox_to_anchor =(0.5,-0.27), loc='lower center',
            ncol=self.numGPUs,frameon=False)
        plt.grid()
        ax = plt.gca()
        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.savefig('utilization4.png',dpi=150,bbox_inches='tight')
        plt.close()
        aplot = Image('utilization4.png')
        aplot.hAlign='LEFT'
        aplot._restrictSize(6.5 * inch, 4 * inch)
        Story.append(aplot)


        doc.build(Story)



def main():

    # command line args (jobID is required)
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="jobId to query", required=True)
    parser.add_argument("--output", help="location for stdout report")
    parser.add_argument("--pdf", help="generate PDF report")
    args = parser.parse_args()

    query = queryMetrics()
    query.set_options(jobID=args.job,output_file=args.output,pdf=args.pdf)
    query.setup()
    query.generate_report_card()

if __name__ == "__main__":
    main()
