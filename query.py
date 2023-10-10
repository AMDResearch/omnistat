#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# MIT License
# 
# Copyright (c) 2023 Advanced Micro Devices, Inc. All Rights Reserved.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -------------------------------------------------------------------------------

from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
import sys
import os
import numpy as np
import subprocess
import argparse
import timeit
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

    def __init__(self):

        # initiate timer
        self.timer_start = timeit.default_timer()

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
        self.sha = "Unknown"

        # Attempt to get current git sha
        cmd = ["git describe --always"]
        results = subprocess.run(cmd, capture_output=True,check=False,shell=True)
        if results.returncode == 0:
            self.sha = results.stdout.decode("utf-8")

    def __del__(self):
        if self.enable_redirect:
            self.output.close()

    def set_options(self,jobID=None,output_file=None,pdf=None):
        if jobID:
            self.jobID=int(jobID)
        if output_file:
            self.output_file = output_file
        if pdf:
            self.pdf = pdf
        return

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
        if self.jobinfo["begin_date"] == "Unknown":
            print("Job %s has not run yet." % self.jobID)
            sys.exit(0)

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

        # Define metrics to report on (set 'title_short' to indicate inclusion in statistics summary)
        self.metrics = [
            {'metric':'rocm_utilization','title':'GPU Core Utilization','title_short':'Utilization (%)'},
            {'metric':'rocm_vram_used','title':'GPU Memory Used (%)','title_short':'Memory Use (%)'},
            {'metric':'rocm_temp_die_edge','title':'GPU Temperature - Die Edge (C)','title_short':'Temperature (C)'},
            {'metric':'rocm_sclk_clock_mhz','title':'GPU Clock Frequency (MHz)'},
            {'metric':'rocm_avg_pwr','title':'GPU Average Power (W)','title_short':'Power (W)'}
            ]

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

        # exit if no jobs found
        if not results[0]:
            print("No job found for id=%i" % id)
            sys.exit(0)

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

    def gather_data(self,saveTimeSeries=False):
        self.stats = {}
        self.time_series = {}
        self.max_GPU_memory_avail = []

        for entry in self.metrics:
            metric = entry['metric']

            self.stats[metric + "_min"]  = []
            self.stats[metric + "_max"]  = []
            self.stats[metric + "_mean"] = []

            if saveTimeSeries:
                self.time_series[metric] = []

            for gpu in range(self.numGPUs):
                times,values = self.query_time_series_data("card" + str(gpu) + "_" + metric)
                
                self.stats[metric + "_max"].append(np.max(values))
                self.stats[metric + "_mean"].append(np.mean(values))
                if metric == 'rocm_vram_used':
                    # compute % memory used
                    times2,values2 = self.query_time_series_data("card" + str(gpu) + "_rocm_vram_total")
                    memoryAvail = np.max(values2)
                    self.stats[metric + "_max"] [-1] = 100.0 * self.stats[metric + "_max"] [-1] / memoryAvail
                    self.stats[metric + "_mean"][-1] = 100.0 * self.stats[metric + "_mean"][-1] / memoryAvail
                    self.max_GPU_memory_avail.append(memoryAvail)
                    values = 100.0 * values / memoryAvail

                if saveTimeSeries:
                    #self.time_series[metric].append([times,values])
                    self.time_series[metric].append({'time':times,'values':values})
        return

    def generate_report_card(self):
        system = "HPC Fund"

        print("")
        print("-" * 40)
        print("HPC Report Card for Job # %i" % self.jobID)
        print("-" * 40)
        print("")
        print("Job Overview (Num Nodes = %i, Machine = %s)" % (len(self.hosts), system))
        print(" --> Start time = %s" % self.start_time)
        print(" --> End   time = %s" % self.end_time.strftime("%Y-%m-%d %H:%M:%S"))
        print("")
        print("GPU Statistics:")
        print("")
        print("    %6s |" % "",end='')
        for entry in self.metrics:
            if 'title_short' in entry:
                #print("%16s |" % entry['title_short'],end='')
                print(" %s |" % entry['title_short'].center(16),end='')
        print("")
        print("    %6s |" % "GPU #",end='')
        for entry in self.metrics:
            if 'title_short' in entry:
                print(" %8s%8s |" % ("Max".center(6),"Mean".center(6)),end='')
        print("")
        print("    " + "-" * 84)

        for card in range(self.numGPUs):
            print("    %6s |" % card,end='')
            for entry in self.metrics:
                if 'title_short' not in entry:
                    continue
                metric = entry['metric']
                print("  %6.2f  %6.2f  |" % (self.stats[metric + "_max"][card],self.stats[metric + "_mean"][card]),end='')
            print("")

        print("")
        print("--")
        print("Query execution time = %.1f secs" % (timeit.default_timer() - self.timer_start))
        print("Version = %s" % self.sha)

        return


            
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

            #--
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

            #--
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

        #--
        # Display general GPU Statistics
        #--

        data = []
        data.append(['','Utilization (%)','','Memory Use (%)','','Temperature (C)','','Power (W)',''])
        data.append(['GPU #','Max','Mean','Max','Mean','Max','Mean','Max','Mean'])

        for gpu in range(self.numGPUs):
            data.append([gpu,
                         "%.2f" % self.stats['rocm_utilization_max'][gpu],   "%.2f" % self.stats['rocm_utilization_mean'][gpu],
                         "%.2f" % self.stats['rocm_vram_used_max'][gpu],     "%.2f" % self.stats['rocm_vram_used_mean'][gpu],
                         "%.2f" % self.stats['rocm_temp_die_edge_max'][gpu], "%.2f" % self.stats['rocm_temp_die_edge_mean'][gpu],
                         "%.2f" % self.stats['rocm_avg_pwr_max'][gpu],       "%.2f" % self.stats['rocm_avg_pwr_mean'][gpu]
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

        #--
        # Display time-series plots
        #--

        Story.append(Spacer(1,0.2*inch))
        Story.append(HRFlowable(width="100%",thickness=1))
        Story.append(Spacer(1,0.2*inch))
        ptext='''<strong>Time Series</strong>'''
        Story.append(Paragraph(ptext,normal))
        Story.append(Spacer(1,0.2*inch))

        for entry in self.metrics:
            metric = entry['metric']
            plt.figure(figsize=(9,2.5))

            for gpu in range(self.numGPUs):
                plt.plot(self.time_series[metric][gpu]['time'],
                         self.time_series[metric][gpu]['values'],linewidth=0.4,label='Card %i' % gpu)
                
            plt.title(entry['title'])
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
            Story.append(aplot)
            os.remove('.utilization.png')

        Story.append(Spacer(1,0.2*inch))
        Story.append(HRFlowable(width="100%",thickness=1))

        footerStyle = ParagraphStyle('footer',
                           fontSize=8,
                           parent=styles['Normal'],
        )

        ptext='''Query execution time = %.1f secs''' % (timeit.default_timer() - self.timer_start)
        Story.append(Paragraph(ptext,footerStyle))
        ptext='''Version = %s''' % self.sha
        Story.append(Paragraph(ptext,footerStyle))
        Story.append(HRFlowable(width="100%",thickness=1))

        # Build the .pdf
        doc.build(Story)
        
        return



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
    query.gather_data(saveTimeSeries=True)
    query.generate_report_card()
    if args.pdf:
        query.dumpFile(args.pdf)

if __name__ == "__main__":
    main()
