import pytest
import requests

from prometheus_api_client import PrometheusConnect

class TestPrometheus:
    url = "http://localhost:9090/"
    node = "node:8000"

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
        results = prometheus.custom_query(f"card0_rocm_avg_pwr{{instance='{self.node}'}}")
        assert len(results) >= 1, "Metric card0_rocm_avg_pwr not available"

        results = prometheus.custom_query(f"card0_rocm_avg_pwr{{instance='{self.node}'}}")
        _, value = results[0]["value"]
        assert int(value) >= 0, "Reported power is too low"
