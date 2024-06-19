# Installation

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

## System-wide deployment

There are different ways to deploy and install Omniwatch in a data center, and
each system will generally require a certain level of customization. This
section first describes the basic manual steps to install the Omniwatch client
and server, and then provides an example of how to deploy Omniwatch in a data
center using Ansible.

### Node-level deployment (client)

The following two subsections describe two different ways of running the
Omniwach client: executing directly from a local directory, or installing it
as a package.

#### Option A. Run client from local directory

1. Clone repository.
   ```
   $ git clone https://github.com/AMDResearch/omniwatch.git
   ```

2. Install dependencies.
   ```
   $ cd omniwatch
   $ pip install --user -r requirements.txt
   ```

3. Launch client with `gunicorn`. Needs to be executed from the root
   directory of the Omniwatch project.
   ```
   $ gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
   ```

#### Option B. Install package

1. Clone repository.
   ```
   $ git clone https://github.com/AMDResearch/omniwatch.git
   ```

2. Create a virtual environment, with Python 3.8, 3.9, or 3.10.
   ```
   $ cd omniwatch
   $ python -m venv /opt/omniwatch
   ```

3. Install omniwatch in a virtual environment. The virtual environment can
   also be used by sourcing the `./opt/omniwatch/bin/activate` file, and that
   way there is no need to keep using the complete `./venv/bin` path every
   time. This guide uses the complete path for clarity. Needs to be
   executed from the root directory of the Omniwatch repository.
   ```
   $ /opt/omniwatch/bin/python -m pip install .
   ```
   Alternatively, use the following line to install Omniwatch with the
   optional dependencies for the `omniwatch-query` tool.
   ```
   $ /opt/omniwatch/bin/python -m pip install .[query]
   ```

4. Launch the client with `gunicorn`. To make sure the installed version of
   Omniwatch is being used, this shouldn't be executed from the root directory
   of the project.
   ```
   $ /opt/omniwatch/bin/gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
   ```

#### Configure client

Launching the Omniwatch client as described above will load the default
configuration options. To use a different configuration file, use the
`OMNIWATCH_CONFIG` environment variable.
```
$ OMNIWATCH_CONFIG=/path/to/config/file gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
```

A [sample configuration
file](https://github.com/AMDResearch/omniwatch/blob/main/omniwatch.default) is
available in the respository.

#### Check installation

As a sanity check, this is the expected output you should see when launching
the Omniwatch client:
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

#### Enable systemd service

To run the Omniwatch client permanently on a host, configure the service via
systemd. An [example service
file](https://github.com/AMDResearch/omniwatch/blob/main/omniwatch.service) is
available in the repository, including the following key lines:
```
Environment="OMNIWATCH_CONFIG=/etc/omniwatch/config"
Environment="OMNIWATCH_PORT=8000"
ExecStart=/opt/omniwatch/bin/gunicorn -b 0.0.0.0:${OMNIWATCH_PORT} "omniwatch.node_monitoring:app"
```
Please set `OMNIWATCH_CONFIG` and `OMNIWATCH_PORT` as needed depending on how
Omniwatch is installed.

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

For a cluster or data center deployment, management tools like Ansible may be
used to install Omniwatch.

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

### Installing Omniwatch

1. Create a virtual environment in a shared directory, with Python 3.8, 3.9,
   or 3.10.
   ```
   $ python -m venv ~/omniwatch
   ```

2. From to root directory of the Omniwatch repository, install omniwatch in
   the virtual environment.
   ```
   $ ~/omniwatch/bin/python -m pip install .[query]
   ```

### Running a SLURM Job

In the SLURM job script, add the following lines to start and stop the data
collection before and after running the application.

```
export OMNIWATCH_CONFIG=~/omniwatch/omniwatch.config

# Start data collector
~/omniwatch/bin/omniwatch-util --start --interval 1

# Run application
sleep 10

# Stop data collector
~/omniwatch/bin/omniwatch-util --stop

# Query server to generate job report
~/omniwatch/bin/omniwatch-util --startserver
~/omniwatch/bin/omniwatch-util --job ${SLURM_JOB_ID}
~/omniwatch/bin/omniwatch-util --stopserver
```

### Exploring results with a local Docker environment

To explore results generated for user-mode executions of Omniwatch, we provide
a Docker environment that will automatically launch the required services
locally. That includes Prometheus to read and query the stored data, and
Grafana as visualization platform to display time series and other metrics.

To explore results:

1. Copy Prometheus data collected with Omniwatch to `./prometheus-data`. The
   entire `datadir` defined in the Omniwatch configuration needs to be copied
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
