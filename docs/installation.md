# Installation

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

## System-wide deployment

Installing Omniwatch in a data center is expected to rely on external tools to
coordinate its deployment, generally with a high level of customization for
each system.

This section first describes the manual steps to install the Omniwatch client
and server, and then provides an example to deploy Omniwatch in a data center
using Ansible.

### Node-level deployment (client)

1. Create a virtual environment, with Python 3.8, 3.9, or 3.10.
   ```
   python -m venv /opt/omniwatch
   ```

2. Install omniwatch in a virtual environment. The virtual environment can
   also be used by sourcing the `./opt/omniwatch/bin/activate` file, and that
   way there is no need to keep using the complete `./venv/bin` path every
   time. This guide uses the complete path for clarity. Needs to be
   executed from the root directory of the Omniwatch repository.
   ```
   /opt/omniwatch/bin/python -m pip install .
   ```
   Alternatively, use the following line to install Omniwatch with the
   optional dependencies for the `omniwatch-query` tool.
   ```
   /opt/omniwatch/bin/python -m pip install .[query]
   ```

3. Launch the client with `gunicorn`.
   ```
   /opt/omniwatch/bin/gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
   ```
   This will read the default configuration file that is installed in the
   package. To use a different configuration file, use the `OMNIWATCH_CONFIG`
   environment variable.
   ```
   OMNIWATCH_CONFIG=/path/to/config/file /opt/omniwatch/bin/gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
   ```
   As a sanity check, this is the expected output you should see when
   launching the Omniwatch client manually:
   ```
   [2024-06-08 18:50:56 -0400] [5834] [INFO] Starting gunicorn 21.2.0
   [2024-06-08 18:50:56 -0400] [5834] [INFO] Listening at: http://0.0.0.0:8000 (5834)
   ...
   Reading runtime-config from omniwatch.ornl
   Runtime library loaded
   SMI library API initialized
   collector_slurm: reading job information from prolog/epilog derived file (/tmp/omni_slurmjobinfo)
   --> [registered] card0_rocm_temp_die_edge -> Temperature (Sensor edge) (C) (gauge)
   --> [registered] card0_rocm_avg_pwr -> Average Graphics Package Power (W) (gauge)
   --> [registered] card0_rocm_sclk_clock_mhz -> sclk clock speed (Mhz) (gauge)
   --> [registered] card0_rocm_mclk_clock_mhz -> mclk clock speed (Mhz) (gauge)
   --> [registered] card0_rocm_vram_total -> VRAM Total Memory (B) (gauge)
   --> [registered] card0_rocm_vram_used -> VRAM Total Used Memory (B) (gauge)
   --> [registered] card0_rocm_utilization -> GPU use (%) (gauge)
   --> [registered] card1_rocm_temp_die_edge -> Temperature (Sensor edge) (C) (gauge)
   --> [registered] card1_rocm_avg_pwr -> Average Graphics Package Power (W) (gauge)
   ```
   In the same node, confirm the client is responding to requests with non-zero
   values for GPU metrics:
   ```
   $ curl localhost:8000/metrics | grep rocm | grep -v "^#"
   rocm_num_gpus 8.0
   card0_rocm_temp_die_edge 32.0
   card0_rocm_avg_pwr 93.0
   card0_rocm_sclk_clock_mhz 1700.0
   card0_rocm_mclk_clock_mhz 1600.0
   card0_rocm_vram_total 6.870269952e+010
   card0_rocm_vram_used 1.0993664e+07
   card0_rocm_utilization 0.0
   ...
   ```

4. To run the Omniwatch client permanently on a host, configure the service via
   systemd. An [example service file](https://github.com/AMDResearch/omniwatch/blob/main/omniwatch.service)
   is available in the repository, including the following key lines:
   ```
   Environment="OMNIWATCH_CONFIG=/etc/omniwatch/config"
   Environment="OMNIWATCH_PORT=8000"
   ExecStart=/opt/omniwatch/bin/gunicorn -b 0.0.0.0:${OMNIWATCH_PORT} "omniwatch.node_monitoring:app"
   ```

In addition to the Omniwatch client, optional standalone scripts are available
in the same installation path:
```
/opt/omniwatch/bin/omniwatch-util # Utility to help run in user mode in SLURM cluster
/opt/omniwatch/bin/omniwatch-annotate # Annotate executions in SLURM jobs
/opt/omniwatch/bin/omniwatch-query # Query server to generate a SLURM job report
```

### Prometheus installation and configuration (server)

On a separate server with access to compute nodes, install and configure
[Prometheus](https://prometheus.io/).

1. Install Prometheus from a package manager, downloading a [precompiled
   binary](https://prometheus.io/download/), or using a [Docker
   image](https://hub.docker.com/u/prom).

   For Debian-based systems:
   ```
   $ apt-get install prometheus
   ```
   For RHEL:
   ```
   $ rpm -ivh golang-github-prometheus
   ```

2. Create a scrape configuration for Prometheus. This configuration controls
   which nodes to poll and at what frequency. For example:
   ```
   scrape_configs:
     - job_name: "omniwatch"
       scrape_interval: 30s
       scrape_timeout: 5s
       static_configs:
         - targets:
           - compute-00:8000
           - compute-01:8000
           - compute-02:8000
           - compute-03:8000
   ```

### Ansible example

For a cluster or data center deployment, management tools like Ansible are
recommended to install Omniwatch.

The following Ansible playbook will fetch the Omniwatch repository in each
node, create a virtual environment for Omniwatch under `/opt/omniwatch`,
install a configuration file under `/etc/omniwatch`, and enable Omniwatch as a
systemd service. This is only an example and will likely need to be adapted
depending on the characteristics and scale of the system.

```
- hosts: all
  vars:
    - omniwatch_url: git@github.com:AMDResearch/omniwatch.git
    - omniwatch_tmp: /tmp/omniwatch-install
    - omniwatch_dir: /opt/omniwatch

  tasks:
    - name: Fetch copy of omniwatch repository for installation
      git:
        repo: "{{ omniwatch_url }}"
        dest: "{{ omniwatch_tmp }}"
        version: jorda/python-package
        single_branch: true

    - name: Install omniwatch in virtual environment
      pip:
        name: "{{ omniwatch_tmp }}[query]"
        virtualenv: "{{ omniwatch_dir }}"
        virtualenv_command: /usr/bin/python3 -m venv

    - name: Create configuration directory
      file:
        path: /etc/omniwatch
        state: directory
        mode: "0755"

    - name: Copy configuration file
      copy:
        remote_src: true
        src: "{{ omniwatch_tmp }}/omniwatch/config/omniwatch.default"
        dest: /etc/omniwatch/config
        mode: "0644"

    - name: Copy service file
      copy:
        remote_src: true
        src: "{{ omniwatch_tmp }}/omniwatch.service"
        dest: /etc/systemd/system
        mode: "0644"

    - name: Enable service
      service:
        name: omniwatch
        enabled: yes
        state: started

    - name: Delete temporary installation files
      file:
        path: "{{ omniwatch_tmp }}"
        state: absent
```

---

## User-mode execution with SLURM

### Local docker environment

