import os
import pytest
import re
import subprocess
import time

from string import Template

import config

slurm_job_template = """\
#!/bin/bash
#SBATCH --job-name=test-usermode
#SBATCH --partition=default-partition
#SBATCH --nodes=$num_nodes
#SBATCH --nodelist=$node_list

export OMNISTAT_CONFIG=/etc/omnistat-user.config
export OMNISTAT_DIR=/source

. /opt/omnistat/bin/activate
cd /jobs

$OMNISTAT_DIR/omnistat-usermode --start --interval 1
$cmd
$OMNISTAT_DIR/omnistat-usermode --stop
"""

class TestJobUser:
    job_file = "slurm-job-user.sh"

    def test_job_multinode(self):
        self.run_job(config.nodes, 10)

    def generate_job_file(self, nodes, cmd):
        num_nodes = len(nodes)
        node_list = ",".join(nodes)

        substitutions = {
            "num_nodes": num_nodes,
            "node_list": node_list,
            "cmd": cmd,
        }

        template = Template(slurm_job_template)
        job = template.safe_substitute(substitutions)

        with open(self.job_file, "w") as f:
            f.write(job)

    def remove_job_file(self):
        os.remove(self.job_file)

    def run_job(self, nodes, seconds):
        self.generate_job_file(nodes, f"srun sleep {seconds}")

        base_exec = ["docker", "exec", "slurm-controller"]
        bash = base_exec + ["bash", "-c"]
        timeout = base_exec + ["timeout", "1m", "bash", "-c"]

        run_cmd = f"cd /jobs && sbatch --parsable /host-source/test/{self.job_file}"
        p = subprocess.run(bash + [run_cmd], capture_output=True, text=True)
        assert p.returncode == 0
        jobid = p.stdout.strip()

        wait_cmd = "until [[ $(squeue -h | wc -l) == 0 ]]; do echo 'Wait...'; sleep 1; done"
        p = subprocess.run(timeout + [wait_cmd], capture_output=True, text=True)
        assert p.returncode == 0

        cat_cmd = f"cat /jobs/slurm-{jobid}.out"
        p = subprocess.run(bash + [cat_cmd], capture_output=True, text=True)
        assert p.returncode == 0

        num_nodes = len(nodes)
        patterns = [
            f"{num_nodes} of {num_nodes} exporters available",
            f"User mode data collectors: SUCCESS",
        ]

        for pattern in patterns:
            assert re.search(pattern, p.stdout) != None

        self.remove_job_file()
