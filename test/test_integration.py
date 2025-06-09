import pytest
import requests
from prometheus_api_client import PrometheusConnect

import config


class TestIntegration:
    def test_request(self):
        response = requests.get(config.prometheus_url)
        assert response.status_code == 200, "Unable to connect to Prometheus"

    @pytest.mark.parametrize("node", config.nodes)
    def test_query_up(self, node):
        prometheus = PrometheusConnect(url=config.prometheus_url)
        results = prometheus.custom_query("up")
        assert len(results) >= 1, "Metric up not available"

        instance = f"{node}:{config.port}"
        results = prometheus.custom_query(f"up{{instance='{instance}'}}")
        _, value = results[0]["value"]
        assert int(value) == 1, "Node exporter not running"

    def test_query_slurm(self):
        prometheus = PrometheusConnect(url=config.prometheus_url)
        results = prometheus.custom_query("rmsjob_info")
        assert len(results) >= 1, "Metric rmsjob_info not available"

    @pytest.mark.skipif(not config.rocm_host, reason="requires ROCm")
    @pytest.mark.parametrize("node", config.nodes)
    def test_query_rocm(self, node):
        prometheus = PrometheusConnect(url=config.prometheus_url)
        instance = f"{node}:{config.port}"
        query = f"rocm_average_socket_power_watts{{instance='{instance}'}}"
        results = prometheus.custom_query(query)
        assert len(results) >= 1, "Metric rocm_average_socket_power_watts not available"

        results = prometheus.custom_query(query)
        _, value = results[0]["value"]
        assert int(value) >= 0, "Reported power is too low"
