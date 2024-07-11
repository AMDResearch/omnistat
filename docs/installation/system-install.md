# System-wide installation

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

There are different ways to deploy and install Omnistat in a data center, and
each system will generally require a certain level of customization. Here, we
provide the basic manual steps to install the Omnistat client
and server, and then provide an example of how to deploy Omnistat in a data
center using Ansible. Finally, an approach for integrating with the SLURM workload manager to track user jobs is discussed.

For system-wide installation, we recommend creation and usage of a dedicated Linux user that will be used to run the data collector daemon of Omnistat (`omnistat-monitor`).  In addition, per the architecture highlighted in {numref}`fig-system-mode`, a separate server (or VM/container) is needed to support installations of a Prometheus server and Grafana instance.  These services can be hosted on your cluster head-node, or via a separate administrative host. Note that if the host chosen to support the Prometheus server can route out externally, you can also leverage public Grafana cloud infrastructure and [forward](https://grafana.com/docs/agent/latest/flow/tasks/collect-prometheus-metrics/) system telemetry data to an external Grafana instance.

To reiterate, the following assumptions are made throughout the rest of this system-wide installation discussion:

__Assumptions__:
* Installer has `sudo` or elevated credentials to install software system-wide, enable systemd services, and optionally modify the local SLURM configuration
* [ROCm](https://rocm.docs.amd.com/en/latest/) v5.7 or newer is pre-installed on all GPU hosts
* Installer has provisioned a dedicated user (eg. `omnidc`) across all desired compute nodes of their system
* Installer has identified a location to host a Prometheus server (if not present already) that has network access to all compute nodes.

## Omnistat software installation

To begin, we download the Omnistat software and install necessary Python dependencies. Per the assumptions above, we leverage a dedicated user to house the software install.

1. Clone repository.
   ```shell-session
   [omnidc@login]$ git clone https://github.com/AMDResearch/omnistat.git
   ```

2. Install dependencies.
   ```shell-session
   [omnidc@login]$ cd omnistat
   [omnidc@login]$ pip install --user -r requirements.txt
   ```

<!-- ```{note}
Omnistat can also be installed as a Python package. How cool is that? Add more snazzy text here to get folks pointed in the 
right direction.
``` -->

At this point, we can verify basic functionality of the data collector and launch the client by hand.

3. Launch data collector (`omnistat-monitor`) interactively.
   ```shell-session
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
configuration options housed within an [omnistat/config/omnistat.default](https://github.com/AMDResearch/omnistat/blob/main/omnistat/config/omnistat.default) file including use of port `8001` for the Prometheus client. If all went well, example output from running `omnistat-monitor` is highlighted below:

```shell-session
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

While the client is running interactively, we can use a _separate_ command shell to query the client to further confirm functionality. The output below highlights an example query response on a system with four GPUS installed (note that the metrics include unique card labels to differentiate specific GPU measurements):

```shell-session
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

Now that the software is installed under a dedicated user and basic functionality has been confirmed, the data collector can be enabled for permanent service. The recommended approach for this is to leverage `systemd` and an example service file named [omnistat.service](https://github.com/AMDResearch/omnistat/blob/main/omnistat.service) is included in the distribution. This contents of the file are shown below with four lines highlighted in yellow that are most likely to require local customization.

<!-- * `User` set to the local Linux user created to run Omnistat
* `OMNISTAT_DIR` set to the local path where you downloaded the source tree
* `OMNISTAT_CONFIG` set to the path of desired runtime config file
* `CPUAffinity` set to the CPU core index where omnistat-monitor will be pinned -->


```eval_rst
.. literalinclude:: omnistat.service
   :emphasize-lines: 8-11
```

Using elevated credentials, install the omnistat.service file across all desired compute nodes (e.g. `/etc/systemd/system/omnistat.service` and enable using systemd (`systemctl  enable omnistat`).

---

## Prometheus server

Once the `omnistat-monitor` daemon is configured and running system-wide, we next install and configure a [Prometheus](https://prometheus.io/) server to enable automatic telemetry collection. This server typically runs on an administrative host and can be installed via package manager, by downloading a [precompiled binary](https://prometheus.io/download/), or using a [Docker image](https://hub.docker.com/u/prom). The install steps below highlights installation via package manager followed by a simple scrape configuration.

<!-- On a separate server with access to compute nodes, install and configure
[Prometheus](https://prometheus.io/). -->

1. Install: Prometheus server (via package manager)

   For Debian-based systems:
   ```shell-session
   # apt-get install prometheus
   ```
   For RHEL:
   ```shell-session
   # rpm -ivh golang-github-prometheus
   ```
   For SUSE:
   ```shell-session
   #  zypper install golang-github-prometheus-prometheus
   ```

2. Configuration: add a scrape configuration to Prometheus to enable telemetry collection. This configuration stanza typically resides in the `/etc/prometheus/prometheus.yml` runtime config file and controls which nodes to poll and at what frequency. The example below highlights addition of an omnistat job that polls for data at 30 second intervals from four separate compute nodes.  We recommend keeping the `scrape_interval` setting at 5 seconds or larger.

   ```
   scrape_configs:
     - job_name: "omnistat"
       scrape_interval: 30s
       scrape_timeout: 5s
       static_configs:
         - targets:
           - compute-00:8001
           - compute-01:8001
           - compute-02:8001
           - compute-03:8001
   ```

Edit your server's prometheus.yml file using the snippet above as a guide and restart the Prometheus server to enable automatic data collection.

```{note}
You may want to adjust the Prometheus server default storage retention policy in order to retain telemetry data longer than the default (which is typically 15 days). Assuming you are using a distro-provided version of Prometheus, you can modify the systemd launch process to include a `--storage.tsdb.retention.time` option as shown in the snippet below:

```text
[Service]
Restart=on-failure
User=prometheus
EnvironmentFile=/etc/default/prometheus
ExecStart=/usr/bin/prometheus $ARGS --storage.tsdb.retention.time=3y
ExecReload=/bin/kill -HUP $MAINPID
TimeoutStopSec=20s
SendSIGKILL=no

```

## Ansible example

For a cluster or data center deployment, configuration management tools like [Ansible](https://github.com/ansible/ansible) may be useful to automate installation of Omnistat.

To aid in this process, the following Ansible playbook will fetch the Omnistat repository on each
node, create a virtual environment for Omnistat under `/opt/omnistat`,
install a configuration file under `/etc/omnistat`, and enable Omnistat as a
systemd service. This example is provided as a starting reference for system administrators and can be adjusted to suit per local conventions.

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