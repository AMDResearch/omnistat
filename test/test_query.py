import logging
import os
import re
import uuid
from pathlib import Path

import numpy as np
import pytest

from omnistat.query import queryMetrics
from omnistat.standalone import push_to_victoria_metrics
from omnistat.utils import readConfig
from test.trace_generator import GPU_METRIC_NAMES, TraceGenerator

test_path = Path(__file__).resolve().parent
CONFIG_FILE = f"{test_path}/docker/victoriametrics/omnistat-query.config"

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
        query.gather_data()
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

    # Validate stats and time series gathered from the query tool when using
    # multiple nodes with different loads.
    #
    # The gpu_values_list parameter is a list of lists (one list of gpu values
    # per node). All gpu_values are expected to have the same length (same
    # number of GPUs in all nodes).
    @pytest.mark.parametrize(
        "num_nodes, gpu_values_list",
        [
            (2, [[0.0], [0.0]]),
            (2, [[100.0], [0.0]]),
            (2, [[0.0], [100.0]]),
            (2, [[100.0], [100.0]]),
            (2, [[25.0], [75.0]]),
            (2, [[100.0, 0.0], [0.0, 0.0]]),
            (4, [[20.0], [40.0], [60.0], [80.0]]),
        ],
    )
    def test_multiple_loads(self, num_nodes, gpu_values_list):
        job_id = uuid.uuid4()
        duration = 60
        interval = 1.0

        trace = TraceGenerator(duration, interval, job_id, num_nodes)
        for i in range(num_nodes):
            trace.add_constant_load(f"load{i}", num_nodes=1, gpu_values=gpu_values_list[i])
        metrics = trace.generate()

        push_to_victoria_metrics(metrics, URL)

        query = queryMetrics("TEST")
        query.set_options(jobID=job_id, interval=interval)
        query.read_config(CONFIG_FILE)
        query.setup()
        query.gather_data(saveTimeSeries=True)

        num_gpus = len(gpu_values_list[0])
        for gpu_values in gpu_values_list:
            assert len(gpu_values) == num_gpus, "All nodes are require the same number of GPUs"

        # Validate time series values and max/mean values from query tool,
        # which are obtained from PromQL queries.
        for gpu_id in range(num_gpus):
            gpu_id_values = [gpu_values[gpu_id] for gpu_values in gpu_values_list]
            expected_max = np.max(gpu_id_values)
            expected_mean = np.mean(gpu_id_values)

            for metric in GPU_METRIC_NAMES:
                query_max = query.stats[f"{metric}_max"][gpu_id]
                query_mean = query.stats[f"{metric}_mean"][gpu_id]
                assert query_max == expected_max, f"Unexpected max value for {metric} in GPU ID {gpu_id}"
                assert query_mean == expected_mean, f"Unexpected mean value for {metric} in GPU ID {gpu_id}"

                for sample_value in query.time_series[metric][gpu_id]["values"]:
                    assert sample_value == expected_mean, f"Unexpected sample value for {metric} in GPU ID {gpu_id}"

    @pytest.mark.parametrize(
        "duration, interval",
        [
            (5, 0.5),
            (10, 1.0),
            (30, 1.0),
            (60, 1.0),
            (60, 5.0),
            (60, 10.0),
            (90, 15.0),
            (180, 30.0),
            (360, 60.0),
        ],
    )
    def test_duration_valid(self, capsys, duration, interval):
        job_id = uuid.uuid4()
        num_nodes = 2
        gpu_values = [100] * num_nodes

        trace = TraceGenerator(duration, interval, job_id, num_nodes)
        trace.add_constant_load("all", num_nodes, gpu_values)
        metrics = trace.generate()

        push_to_victoria_metrics(metrics, URL)

        query = queryMetrics("TEST")
        query.set_options(jobID=job_id, interval=interval)
        query.read_config(CONFIG_FILE)
        try:
            query.setup()
        except SystemExit:
            captured = capsys.readouterr()
            output = captured.out
            pytest.fail("Unexpected exit with sys.exit()")

    @pytest.mark.parametrize(
        "duration, interval",
        [
            (1, 1.0),  # 1 sample
            (5, 5.0),  # 1 sample
            (1, 0.5),  # 2 samples
            (60, 30.0),  # 2 samples
        ],
    )
    def test_min_num_samples(self, capsys, caplog, duration, interval):
        caplog.set_level(logging.INFO)

        job_id = uuid.uuid4()
        num_nodes = 1
        gpu_values = [100] * num_nodes

        trace = TraceGenerator(duration, interval, job_id, num_nodes)
        trace.add_constant_load("all", num_nodes, gpu_values)
        metrics = trace.generate()

        push_to_victoria_metrics(metrics, URL)

        query = queryMetrics("TEST")
        query.set_options(jobID=job_id, interval=interval)
        query.read_config(CONFIG_FILE)
        with pytest.raises(SystemExit) as exit_info:
            query.setup()
        assert exit_info.type == SystemExit
        assert exit_info.value.code == None

        # Capture and validate expected logging message
        assert len(caplog.records) > 1
        record = caplog.records[-1]
        assert record.levelname == "INFO"
        pattern = f"Need at least [0-9]+ samples to query"
        assert re.search(pattern, record.message) != None, f"Unexpected output: {record.message}"
