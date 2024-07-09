# System-wide installation

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

There are different ways to deploy and install Omnistat in a data center, and
each system will generally require a certain level of customization. Here, we
provide the basic manual steps to install the Omnistat client
and server, and then provides an example of how to deploy Omnistat in a data
center using Ansible. Finally, an approach for integrating with the SLURM workload manager to track user jobs is discussed.

For system-wide installation, we recommend creation and usage of a dedicated Linux user that will be used to run the data collector daemon of Omnistat (`omnistat-monitor`).  In addition, per the architecture highlighted in {numref}`fig-system-mode`, a separate server (or VM/container) is needed to support installations of a Prometheus server and Grafana instance.  These services can be hosted on your cluster head-node, or via a separate administrative host. Note that if the host chosen to support the Prometheus server can route out externally, you can also leverage public Grafana cloud infrastructure and [forward](https://grafana.com/docs/agent/latest/flow/tasks/collect-prometheus-metrics/) system telemetry data to an external Grafana instance.

To reiterate, the following assumptions are made throughout the rest of this system-wide installation discussion:

__Assumptions__:
* Installer has `sudo` or elevated credentials to install software system-wide, enable systemd services, and optionally modify the local SLURM configuration
* [ROCm](https://rocm.docs.amd.com/en/latest/) v5.7 or newer is installed on all GPU hosts
* Installer has provisioned a dedicated user (eg. `omnidc`) across all desired compute nodes of their system
* Installer has identified a location to host a Prometheus server (if not present already) that has network access to all compute nodes.

## Software installation

To begin, we download the Omnistat software and install necessary Python dependencies. Per the assumptions above, we leverage a dedicated user to house the software install.

<!-- The following two subsections describe two different ways of running the
Omniwach client: executing directly from a local directory, or installing it
as a package. -->

<!-- ### Option A. Run client from local directory -->

1. Clone repository.
   ```
   [omnidc@login]$ git clone https://github.com/AMDResearch/omnistat.git
   ```

2. Install dependencies.
   ```
   [omnidc@login]$ cd omnistat
   [omnidc@login]$ pip install --user -r requirements.txt
   ```

```{note}
Omnistat can also be installed as a Python package. How cool is that? Add more snazzy text here to get folks pointed in the 
right direction.
```

At this point, we can verify basic functionality of the data collector and launch the client by hand.

3. Launch data collector (`omnistat-monitor`) interactively.
   ```
   [omnidc@login]$ ./omnistat-monitor
   ```

<!-- ### Option B. Install package

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
   ``` -->

<!-- ### Configure client -->

Launching the data collector client as described above will use a set of default
configuration options housed within a [omnistat/config/omnistat.default](https://github.com/AMDResearch/omnistat/blob/main/omnistat/config/omnistat.default) file including use of port `8001` for the Prometheus client. If all went well, example output from running `omnistat-monitor` is highlighted below:

```text
Reading configuration from /home1/omnidc/omnistat/omnistat/config/omnistat.default
Allowed query IPs = ['127.0.0.1']
Disabling SLURM collector via host_skip match (login.*)
Runtime library loaded from /opt/rocm-6.0.2/lib/librocm_smi64.so
SMI library API initialized
SMI version >= 6
Number of GPU devices = 4
GPU topology indexing: Scanning devices from /sys/class/kfd/kfd/topology/nodes
--> Mapping: {0: '3', 1: '2', 2: '1', 3: '0'}
--> [registered] rocm_temperature_edge_celsius -> Temperature (Sensor edge) (C) (gauge)
--> [registered] rocm_average_socket_power_watts -> Average Graphics Package Power (W) (gauge)
--> [registered] rocm_sclk_clock_mhz -> current sclk clock speed (Mhz) (gauge)
--> [registered] rocm_mclk_clock_mhz -> current mclk clock speed (Mhz) (gauge)
--> [registered] rocm_vram_total_bytes -> VRAM Total Memory (B) (gauge)
--> [registered] rocm_vram_used_percentage -> VRAM Memory in Use (%) (gauge)
--> [registered] rocm_utilization_percentage -> GPU use (%) (gauge)
[2024-07-09 13:19:33 -0500] [2995880] [INFO] Starting gunicorn 21.2.0
[2024-07-09 13:19:33 -0500] [2995880] [INFO] Listening at: http://0.0.0.0:8001 (2995880)
[2024-07-09 13:19:33 -0500] [2995880] [INFO] Using worker: sync
[2024-07-09 13:19:33 -0500] [2995881] [INFO] Booting worker with pid: 2995881
```

```{note}
You can override the default runtime configuration file above by setting an `OMNISTAT_CONFIG` environment variable or by using the `./omnistat-monitor --configfile` option.
```

While the client is running interactively, we can use a _separate_ command shell to query the client to further confirm functionality. On a system with four GPUS installed, expect responses like the following where metrics are organized with unique card labels:

```text
[omnidc@login]$ curl localhost:8001/metrics | grep rocm | grep -v "^#"
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

### Enable systemd service

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

## Prometheus installation and configuration (server)

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

## Ansible example

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