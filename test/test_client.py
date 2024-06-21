import os
import pytest
import requests
import time

from prometheus_api_client import PrometheusConnect

class TestPrometheus:
    url = "http://localhost:9090/"
    node = "node:8000"
    time_range = "30m"

    def test_request(self):
        response = requests.get(self.url)
        assert response.status_code == 200, "Unable to connect to Prometheus"

    def test_query_up(self):
        prometheus = PrometheusConnect(url=self.url)
        results = prometheus.custom_query("up")
        assert len(results) >= 1, "Metric up not available"

        results = prometheus.custom_query(f"up{{instance='{self.node}'}}")
        _, value = results[0]["value"]
        assert int(value) == 1, "Node exporter not running"

    def test_query_slurm(self):
        prometheus = PrometheusConnect(url=self.url)
        results = prometheus.custom_query("slurmjob_info")
        assert len(results) >= 1, "Metric slurmjob_info not available"

    def test_query_rocm(self):
        prometheus = PrometheusConnect(url=self.url)
        query = f"card0_rocm_avg_pwr{{instance='{self.node}'}}"
        results = prometheus.custom_query(query)
        assert len(results) >= 1, "Metric card0_rocm_avg_pwr not available"

        results = prometheus.custom_query(query)
        _, value = results[0]["value"]
        assert int(value) >= 0, "Reported power is too low"

    def test_job(self):
        prometheus = PrometheusConnect(url=self.url)
        query = f"slurmjob_info{{jobid=~'.+'}}[{self.time_range}]"
        results = prometheus.custom_query(query)

        last_jobid = 0
        if len(results) != 0:
            last_job = max(results, key=lambda x: int(x["metric"]["jobid"]))
            last_jobid = int(last_job["metric"]["jobid"])

        job_seconds = 2
        self.run_job(job_seconds)
        time.sleep(job_seconds + 1)

        results = prometheus.custom_query(query)
        job = max(results, key=lambda x: int(x["metric"]["jobid"]))
        jobid = int(job["metric"]["jobid"])
        assert jobid == last_jobid + 1, "One job should have been executed"

        num_samples = len(job["values"])
        assert num_samples == job_seconds , "Expected one sample per second"

    # Execute an empty job lasting a given amount of seconds
    def run_job(self, seconds):
        sbatch_cmd = f"sbatch --wrap=\"sleep {seconds}\""
        exec_cmd = f"docker exec slurm-controller-1 bash -c 'cd /jobs; {sbatch_cmd}'"
        os.system(exec_cmd)
