import os
import re
import uuid
from pathlib import Path

import pytest

from omnistat.query import queryMetrics
from omnistat.standalone import push_to_victoria_metrics
from omnistat.utils import readConfig
from test.trace_generator import TraceGenerator

test_path = Path(__file__).resolve().parent
CONFIG_FILE = f"{test_path}/test_query.config"

config = readConfig(CONFIG_FILE)
URL = config["omnistat.query"]["prometheus_url"]


class TestQuery:
    # Validate job reports from the query tool by generating traces with known
    # values in all samples.
    #
    # The parametrized variables include:
    #  - num_nodes: Number of nodes in the trace
    #  - gpu_values: List of values for all GPU metrics, indexed by GPU ID (so the
    #    length of the list is the number of GPUs in each node).
    #
    # Examples:
    #  - (1, [0.0]): 1 node, 1 GPU/node, all metrics have a value of 0.0.
    #  - (1, [50.0, 50.0]): 1 nodes, 2 GPUs/node, all metrics have a value of
    #    50.0 in all GPUs.
    #  - (2, [25.0, 75.0]): 2 nodes, 2 GPUs/node, metrics on GPU ID 0 have a
    #    value of 25.0, and metrics on GPU ID 1 have a value of 75.0.
    @pytest.mark.parametrize(
        "num_nodes, gpu_values",
        [
            (1, [0.0]),
            (1, [100.0]),
            (1, [0.0, 0.0]),
            (1, [100.0, 100.0]),
            (1, [0.0, 50.0, 100.0]),
            (2, [0.0]),
            (2, [100.0]),
            (2, [0.0, 0.0]),
            (2, [100.0, 100.0]),
            (2, [0.0, 50.0, 100.0]),
        ],
    )
    def test_job_report(self, capsys, num_nodes, gpu_values):
        job_id = uuid.uuid4()
        duration = 60
        interval = 1.0

        trace = TraceGenerator(duration, interval, job_id, num_nodes)
        trace.add_constant_load("all", num_nodes, gpu_values)
        metrics = trace.generate()

        push_to_victoria_metrics(metrics, URL)

        query = queryMetrics("TEST")
        query.set_options(jobID=job_id, interval=interval)
        query.read_config(CONFIG_FILE)
        query.setup()
        query.gather_data(saveTimeSeries=True)
        query.generate_report_card()

        # Capture report from stdout to validate results
        captured = capsys.readouterr()
        report = captured.out

        # From the report, parse the summary table aggregated by GPU IDs
        pattern = re.compile(r"[\s]+[0-9]+[\s]+\|")
        table = [line for line in report.splitlines() if re.match(pattern, line)]
        report_values = {}
        for row in table:
            row = row.strip().split("|")
            gpu_id = int(row[0].strip())
            values = [v for metric in row[1:] for v in metric.split()]
            report_values[gpu_id] = values

        assert len(report_values) == len(gpu_values), "Unexpected number of GPUs in the report"

        for gpu_id, values in report_values.items():
            assert len(values) == 8, "Unexpected number of columns in the report"
            for v in values:
                assert float(v) == gpu_values[gpu_id], "Unexpected metric value"
