# Installation

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

## System-wide deployment

There are different ways to deploy and install Omnistat in a data center, and
each system will generally require a certain level of customization. This
section first describes the basic manual steps to install the Omnistat client
and server, and then provides an example of how to deploy Omnistat in a data
center using Ansible.

### Node-level deployment (client)

The following two subsections describe two different ways of running the
Omniwach client: executing directly from a local directory, or installing it
as a package.

#### Option A. Run client from local directory

1. Clone repository.
   ```
   $ git clone https://github.com/AMDResearch/omnistat.git
   ```

2. Install dependencies.
   ```
   $ cd omnistat
   $ pip install --user -r requirements.txt
   ```

3. Launch client with `gunicorn`. Needs to be executed from the root
   directory of the Omnistat project.
   ```
   $ gunicorn -b 0.0.0.0:8000 "omnistat.node_monitoring:app"
   ```

#### Option B. Install package

1. Clone repository.
   ```
   $ git clone https://github.com/AMDResearch/omnistat.git
   ```

2. Create a virtual environment, with Python 3.8, 3.9, or 3.10.
   ```
   $ cd omnistat
   $ python -m venv /opt/omnistat
   ```

3. Install omnistat in a virtual environment. The virtual environment can
   also be used by sourcing the `./opt/omnistat/bin/activate` file, and that
   way there is no need to keep using the complete `./venv/bin` path every
   time. This guide uses the complete path for clarity. Needs to be
   executed from the root directory of the Omnistat repository.
   ```
   $ /opt/omnistat/bin/python -m pip install .
   ```
   Alternatively, use the following line to install Omnistat with the
   optional dependencies for the `omnistat-query` tool.
   ```
   $ /opt/omnistat/bin/python -m pip install .[query]
   ```

4. Launch the client with `gunicorn`. To make sure the installed version of
   Omnistat is being used, this shouldn't be executed from the root directory
   of the project.
   ```
   $ /opt/omnistat/bin/gunicorn -b 0.0.0.0:8000 "omnistat.node_monitoring:app"
   ```

#### Configure client

Launching the Omnistat client as described above will load the default
configuration options. To use a different configuration file, use the
`OMNISTAT_CONFIG` environment variable.
```
$ OMNISTAT_CONFIG=/path/to/config/file gunicorn -b 0.0.0.0:8000 "omnistat.node_monitoring:app"
```

A [sample configuration
file](https://github.com/AMDResearch/omnistat/blob/main/omnistat.default) is
available in the respository.

#### Check installation

As a sanity check, this is the expected output you should see when launching
the Omnistat client:
```
[2024-06-08 18:50:56 -0400] [5834] [INFO] Starting gunicorn 21.2.0
[2024-06-08 18:50:56 -0400] [5834] [INFO] Listening at: http://0.0.0.0:8000 (5834)
...
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
...
```
In the same node, confirm the client is responding to requests with non-zero
values for GPU metrics:
```
$ curl localhost:8000/metrics | grep rocm | grep -v "^#"
rocm_num_gpus 4.0
rocm_temperature_edge_celsius{card="3"} 40.0
rocm_temperature_edge_celsius{card="2"} 43.0
rocm_temperature_edge_celsius{card="1"} 43.0
rocm_temperature_edge_celsius{card="0"} 42.0
rocm_average_socket_power_watts{card="3"} 35.0
rocm_average_socket_power_watts{card="2"} 33.0
rocm_average_socket_power_watts{card="1"} 35.0
rocm_average_socket_power_watts{card="0"} 35.0
...
```

#### Enable systemd service

To run the Omnistat client permanently on a host, configure the service via
systemd. An [example service
file](https://github.com/AMDResearch/omnistat/blob/main/omnistat.service) is
available in the repository, including the following key lines:
```
Environment="OMNISTAT_CONFIG=/etc/omnistat/config"
Environment="OMNISTAT_PORT=8000"
ExecStart=/opt/omnistat/bin/gunicorn -b 0.0.0.0:${OMNISTAT_PORT} "omnistat.node_monitoring:app"
```
Please set `OMNISTAT_CONFIG` and `OMNISTAT_PORT` as needed depending on how
Omnistat is installed.

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
     - job_name: "omnistat"
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

For a cluster or data center deployment, management tools like Ansible may be
used to install Omnistat.

The following Ansible playbook will fetch the Omnistat repository in each
node, create a virtual environment for Omnistat under `/opt/omnistat`,
install a configuration file under `/etc/omnistat`, and enable Omnistat as a
systemd service. This is only an example and will likely need to be adapted
depending on the characteristics and scale of the system.

```
- hosts: all
  vars:
    - omnistat_url: git@github.com:AMDResearch/omnistat.git
    - omnistat_tmp: /tmp/omnistat-install
    - omnistat_dir: /opt/omnistat

  tasks:
    - name: Fetch copy of omnistat repository for installation
      git:
        repo: "{{ omnistat_url }}"
        dest: "{{ omnistat_tmp }}"
        version: jorda/python-package
        single_branch: true

    - name: Install omnistat in virtual environment
      pip:
        name: "{{ omnistat_tmp }}[query]"
        virtualenv: "{{ omnistat_dir }}"
        virtualenv_command: /usr/bin/python3 -m venv

    - name: Create configuration directory
      file:
        path: /etc/omnistat
        state: directory
        mode: "0755"

    - name: Copy configuration file
      copy:
        remote_src: true
        src: "{{ omnistat_tmp }}/omnistat/config/omnistat.default"
        dest: /etc/omnistat/config
        mode: "0644"

    - name: Copy service file
      copy:
        remote_src: true
        src: "{{ omnistat_tmp }}/omnistat.service"
        dest: /etc/systemd/system
        mode: "0644"

    - name: Enable service
      service:
        name: omnistat
        enabled: yes
        state: started

    - name: Delete temporary installation files
      file:
        path: "{{ omnistat_tmp }}"
        state: absent
```

---

## User-mode execution with SLURM

### Installing Omnistat

1. Create a virtual environment in a shared directory, with Python 3.8, 3.9,
   or 3.10.
   ```
   $ python -m venv ~/omnistat
   ```

2. From to root directory of the Omnistat repository, install omnistat in
   the virtual environment.
   ```
   $ ~/omnistat/bin/python -m pip install .[query]
   ```

### Running a SLURM Job

In the SLURM job script, add the following lines to start and stop the data
collection before and after running the application.

```
export OMNISTAT_CONFIG=~/omnistat/omnistat.config

# Start data collector
~/omnistat/bin/omnistat-util --start --interval 1

# Run application
sleep 10

# Stop data collector
~/omnistat/bin/omnistat-util --stop

# Query server to generate job report
~/omnistat/bin/omnistat-util --startserver
~/omnistat/bin/omnistat-util --job ${SLURM_JOB_ID}
~/omnistat/bin/omnistat-util --stopserver
```

### Exploring results with a local Docker environment

To explore results generated for user-mode executions of Omnistat, we provide
a Docker environment that will automatically launch the required services
locally. That includes Prometheus to read and query the stored data, and
Grafana as visualization platform to display time series and other metrics.

To explore results:

1. Copy Prometheus data collected with Omnistat to `./prometheus-data`. The
   entire `datadir` defined in the Omnistat configuration needs to be copied
   (e.g. a `data` directory should be present under `./prometheus-data`).
2. Start services:
   ```
   $ export PROMETHEUS_USER="$(id -u):$(id -g)"
   $ docker compose up -d
   ```
   User and group IDs are exported with the `PROMETHEUS_USER` variable to ensure
   the container has the right permissions to read the local data under the
   `./prometheus-data` directory.
4. Access Grafana dashboard at [http://localhost:3000](http://localhost:3000).
   Note that starting Grafana can take a few seconds.
5. Stop services:
   ```
   $ docker compose down
   ```
