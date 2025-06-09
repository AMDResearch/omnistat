import time

import numpy as np

GPU_METRIC_NAMES = [
    "rocm_utilization_percentage",
    "rocm_vram_used_percentage",
    "rocm_temperature_celsius",
    "rocm_sclk_clock_mhz",
    "rocm_average_socket_power_watts",
]


class TraceGenerator:
    """
    Generate synthetic Omnistat traces. A trace consists of one or more
    "loads", where a load represents a collection of nodes exhibiting identical
    behavior.
    """

    def __init__(self, duration: int, interval: float, job_id: str, num_nodes: int):
        # Simulate time progression starting from roughly the current time:
        # generate metrics as if they happened in the past leading up to 'now'.
        start_time = int(time.time()) - duration
        samples = list(np.arange(0.0, duration, interval))
        self.times = [int((start_time + i) * 1000) for i in samples]

        self.job_id = job_id
        self.num_nodes = num_nodes

        self.loads = {}

    def add_constant_load(self, load_id: str, num_nodes: int, gpu_values: list[float]):
        """
        Adds a load with constant values. Values can be defined for each GPU
        ID, and will remain the same for all metrics and samples in all the
        nodes that are part of the load.

        Args:
            load_id (str): Unique string to identify load within the trace.
            num_nodes (int): Number of nodes in this load.
            gpu_values (list): List of values to use, indexed by GPU ID.
        """
        self.loads[load_id] = (num_nodes, gpu_values)

    def generate(self):
        total_num_nodes = 0
        for _, (num_nodes, _) in self.loads.items():
            total_num_nodes += num_nodes
        assert self.num_nodes == total_num_nodes, "Number of nodes doesn't match load"

        metrics = []
        for load_id, (num_nodes, gpu_values) in self.loads.items():
            nodes = [f"node-{i}.{load_id}.{self.job_id}" for i in range(num_nodes)]
            for node in nodes:
                info_labels = [
                    f'instance="{node}"',
                    f'nodes="{self.num_nodes}"',
                    f'jobid="{self.job_id}"',
                    f'jobstep=""',
                    f'partition="test"',
                ]
                info_metric = [f'rmsjob_info{{{",".join(info_labels)}}} 1 {t}' for t in self.times]
                metrics.extend(info_metric)

                num_gpus = len(gpu_values)
                num_gpus_labels = [
                    f'instance="{node}"',
                ]
                num_gpus_metric = [f'rocm_num_gpus{{{",".join(info_labels)}}} {num_gpus} {t}' for t in self.times]
                metrics.extend(num_gpus_metric)

                for gpu_id, value in enumerate(gpu_values):
                    for name in GPU_METRIC_NAMES:
                        gpu_metric = [f'{name}{{instance="{node}",card="{gpu_id}"}} {value} {t}' for t in self.times]
                        metrics.extend(gpu_metric)

        return metrics
