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
        <strong>HPC Report Card</strong>: JobID = %s<br/>
        <strong>Start Time</strong>: %s<br/>
        <strong>End Time</strong>: %s<br/>
        ''' % (self.jobID,self.start_time,self.end_time.strftime("%Y-%m-%d %H:%M:%S"))
        Story.append(Paragraph(ptext, styles["Bullet"]))
        Story.append(HRFlowable(width="100%",thickness=2))
        
#             <strong>JobID</strong>: %s<br/>
        # generate Utilization Table
        Story.append(Spacer(1,0.2*inch))
        ptext='''<strong>GPU Statistics</strong>'''
        Story.append(Paragraph(ptext,normal))
        Story.append(Spacer(1,0.2*inch))
        #Story.append(HRFlowable(width="100%",thickness=1))

        # Get time series data and compute some stats...

        plots = [{'title':'GPU Core Utilization','metric':'rocm_utilization'},
                 {'title':'GPU Memory Used (%)','metric':'rocm_vram_used'},
                 {'title':'GPU Temperature - Die Edge (C)','metric':'rocm_temp_die_edge'},
                 {'title':'GPU Clock Frequency (MHz)','metric':'rocm_slck_clock_mhz'},
                 {'title':'GPU Average Power (W)','metric':'rocm_avg_pwr'}]
        
        stats = {}

        timeSeries = []

        for plot in plots:
            metric = plot['metric']
            plt.figure(figsize=(9,2.5))

            stats[metric + "_min"] = []
            stats[metric + "_max"] = []
            stats[metric + "_mean"] = []

            for gpu in range(self.numGPUs):
                times,values = self.query_time_series_data("card" + str(gpu) + "_" + metric)
                
                stats[metric + "_min"].append(np.min(values))
                stats[metric + "_max"].append(np.max(values))
                stats[metric + "_mean"].append(np.mean(values))
                if metric == 'rocm_vram_used':
                    times2,values2 = self.query_time_series_data("card" + str(gpu) + "_rocm_vram_total")
                    memoryAvail = np.max(values2)
                    plt.plot(times,100.0 * values / memoryAvail,linewidth=0.4,label='Card %i' % gpu)
                    stats[metric + "_max"][-1]  = 100.0 * stats[metric + "_max"][-1] / memoryAvail
                    stats[metric + "_mean"][-1] = 100.0 * stats[metric + "_mean"][-1] / memoryAvail
                    #plt.ylim([0,100])
                else:
                    plt.plot(times,values,linewidth=0.4,label='Card %i' % gpu)

            plt.title(plot['title'])
            plt.legend(bbox_to_anchor =(0.5,-0.27), loc='lower center', ncol=self.numGPUs,frameon=False)
            plt.grid()
            ax = plt.gca()

            locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
            formatter = mdates.ConciseDateFormatter(locator)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            plt.savefig('.utilization.png',dpi=150,bbox_inches='tight')
            plt.close()
            aplot = Image('.utilization.png')
            aplot.hAlign='LEFT'
            aplot._restrictSize(6.5 * inch, 4 * inch)
            #Story.append(aplot)
            timeSeries.append(aplot)

        #--
        # Display general GPU Statistics
        #--

        data = []
        data.append(['','Utilization (%)','','Memory Use (%)','','Temperature (C)','','Power (W)',''])
        data.append(['GPU #','Max','Mean','Max','Mean','Max','Mean','Max','Mean'])

        for gpu in range(self.numGPUs):
            data.append([gpu,
                         "%.2f" % stats['rocm_utilization_max'][gpu],"%.2f" % stats['rocm_utilization_mean'][gpu],
                         "%.2f" % stats['rocm_vram_used_max'][gpu], "%.2f" % stats['rocm_vram_used_mean'][gpu],
                         "%.2f" % stats['rocm_temp_die_edge_max'][gpu], "%.2f" % stats['rocm_temp_die_edge_mean'][gpu],
                         "%.2f" % stats['rocm_avg_pwr_max'][gpu], "%.2f" % stats['rocm_avg_pwr_mean'][gpu]
            ])

        t=Table(data,rowHeights=[.21*inch] * len(data),
            colWidths=[0.55*inch,0.72*inch])
        t.hAlign='LEFT'
        t.setStyle(TableStyle([('LINEBELOW',(0,1),(-1,1),1.5,colors.black),
                              ('ALIGN',(0,0),(-1,-1),'CENTER')]))
        t.setStyle(TableStyle([('LINEBEFORE',(1,0),(1,-1),1.25,colors.darkgrey),
                               ('LINEAFTER', (2,0),(2,-1),1.25,colors.darkgrey),
                               ('LINEAFTER', (4,0),(4,-1),1.25,colors.darkgrey),
                               ('LINEAFTER', (6,0),(6,-1),1.25,colors.darkgrey)
                               ]))
        t.setStyle(TableStyle([('SPAN',(1,0),(2,0)),
                               ('SPAN',(3,0),(4,0)),
                               ('SPAN',(5,0),(6,0)),
                               ('SPAN',(7,0),(8,0))
                               ]))

        for each in range(2,len(data)):
            if each % 2 == 0:
                bg_color = colors.lightgrey
            else:
                bg_color = colors.whitesmoke

            t.setStyle(TableStyle([('BACKGROUND', (0, each), (-1, each), bg_color)]))
        Story.append(t)



        # add Time-series plots (assembled previously)
        Story.append(Spacer(1,0.2*inch))
        Story.append(HRFlowable(width="100%",thickness=1))
        Story.append(Spacer(1,0.2*inch))
        ptext='''<strong>Time Series</strong>'''
        Story.append(Paragraph(ptext,normal))
        Story.append(Spacer(1,0.2*inch))

        for image in timeSeries:
            Story.append(image)

        # Buiild the .pdf
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
