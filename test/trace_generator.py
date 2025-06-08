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
            info = [f'rmsjob_info{{instance="{node}",jobid="{self.job_id}"}} 1 {t}' for t in self.times]
            self.metrics.extend(info)
            for gpu_id, value in enumerate(gpu_values):
                for name in GPU_METRIC_NAMES:
                    gpu_metric = [f'{name}{{instance="{node}",card="{gpu_id}"}} {value} {t}' for t in self.times]
                    self.metrics.extend(gpu_metric)
