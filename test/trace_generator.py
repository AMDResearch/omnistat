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
    def __init__(self, duration, interval, job_id):
        # Simulate time progression starting from roughly the current time:
        # generate metrics as if they happened in the past leading up to 'now'.
        start_time = int(time.time()) - duration
        samples = list(np.arange(0.0, duration, interval))
        self.times = [int((start_time + i) * 1000) for i in samples]

        self.metrics = []
        self.job_id = job_id

    def add_static_load(self, load_id, num_nodes, gpu_values):
        nodes = [f"node-{i}.{load_id}.{self.job_id}" for i in range(num_nodes)]
        for node in nodes:
            info_labels = [
                f'instance="{node}"',
                f'nodes="{num_nodes}"',
                f'jobid="{self.job_id}"',
                f'jobstep=""',
                f'partition="test"',
            ]
            info_metric = [f'rmsjob_info{{{",".join(info_labels)}}} 1 {t}' for t in self.times]
            self.metrics.extend(info_metric)

            num_gpus = len(gpu_values)
            num_gpus_labels = [
                f'instance="{node}"',
            ]
            num_gpus_metric = [f'rocm_num_gpus{{{",".join(info_labels)}}} {num_gpus} {t}' for t in self.times]
            self.metrics.extend(num_gpus_metric)

            for gpu_id, value in enumerate(gpu_values):
                for name in GPU_METRIC_NAMES:
                    gpu_metric = [f'{name}{{instance="{node}",card="{gpu_id}"}} {value} {t}' for t in self.times]
                    self.metrics.extend(gpu_metric)
