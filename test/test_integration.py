import os
import pytest
import requests
import shutil
import time

import pytest

from prometheus_api_client import PrometheusConnect

# Variable used to skip tests that depend on a ROCm installation; assume
# ROCm is installed if we can find `rocminfo' in the host.
rocm_host = True if shutil.which("rocminfo") else False

# List of available nodes in the test environment.
nodes = ["node1", "node2"]


class TestIntegration:
    url = "http://localhost:9090/"
    port = "8000"
    time_range = "30m"

    def test_request(self):
        response = requests.get(self.url)
        assert response.status_code == 200, "Unable to connect to Prometheus"

    @pytest.mark.parametrize("node", nodes)
    def test_query_up(self, node):
        prometheus = PrometheusConnect(url=self.url)
        results = prometheus.custom_query("up")
        assert len(results) >= 1, "Metric up not available"

        instance = f"{node}:{self.port}"
        results = prometheus.custom_query(f"up{{instance='{instance}'}}")
        _, value = results[0]["value"]
        assert int(value) == 1, "Node exporter not running"

    def test_query_slurm(self):
        prometheus = PrometheusConnect(url=self.url)
        results = prometheus.custom_query("rmsjob_info")
        assert len(results) >= 1, "Metric rmsjob_info not available"

    @pytest.mark.skipif(not rocm_host, reason="requires ROCm")
    @pytest.mark.parametrize("node", nodes)
    def test_query_rocm(self, node):
        prometheus = PrometheusConnect(url=self.url)
        instance = f"{node}:{self.port}"
        query = f"rocm_average_socket_power_watts{{instance='{instance}'}}"
        results = prometheus.custom_query(query)
        assert len(results) >= 1, "Metric rocm_average_socket_power_watts not available"

        results = prometheus.custom_query(query)
        _, value = results[0]["value"]
        assert int(value) >= 0, "Reported power is too low"

    @pytest.mark.parametrize("node", nodes)
    def test_job(self, node):
        prometheus = PrometheusConnect(url=self.url)
        last_jobid, _ = self.query_last_job(prometheus)

        job_seconds = 2
        self.run_job([node], job_seconds)
        time.sleep(job_seconds + 1)

        jobid, series = self.query_last_job(prometheus)
        assert jobid == last_jobid + 1, "One job should have been executed"
        assert len(series) == 1, "Expected a different number of series"

        num_samples = len(series[0]["values"])
        assert (
            num_samples == job_seconds or num_samples == job_seconds + 1
        ), "Expected approximately one sample per second"

    def test_job_multinode(self):
        prometheus = PrometheusConnect(url=self.url)
        last_jobid, _ = self.query_last_job(prometheus)

        job_seconds = 2
        self.run_job(nodes, job_seconds)
        time.sleep(job_seconds + 1)

        jobid, series = self.query_last_job(prometheus)
        assert jobid == last_jobid + 1, "One job should have been executed"
        assert len(series) == len(nodes), "Expected a different number of series"

        for instance in series:
            num_samples = len(instance["values"])
            assert (
                num_samples == job_seconds or num_samples == job_seconds + 1
            ), "Expected approximately one sample per second"

    # Get ID and metrics for the most recently executed job
    def query_last_job(self, prometheus):
        jobid = 0
        series = None

        query = f"rmsjob_info{{jobid=~'.+'}}[{self.time_range}]"
        results = prometheus.custom_query(query)
        if len(results) != 0:
            last_job_metric = max(results, key=lambda x: int(x["metric"]["jobid"]))
            jobid = int(last_job_metric["metric"]["jobid"])
            query = f"rmsjob_info{{jobid='{jobid}'}}[{self.time_range}]"
            series = prometheus.custom_query(query)

        return (jobid, series)

    # Execute an empty job lasting a given amount of seconds
    def run_job(self, nodes, seconds):
        nodelist = ",".join(nodes)
        sbatch_cmd = f'sbatch --nodes={len(nodes)} --nodelist={nodelist} --wrap="srun sleep {seconds}"'
        exec_cmd = f"docker exec slurm-controller bash -c 'cd /jobs; {sbatch_cmd}'"
        os.system(exec_cmd)
