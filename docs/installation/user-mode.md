# User-mode execution

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

In user-mode executions, Omnistat data collectors and a companion Prometheus
server are deployed temporarily on hosts assigned to a user's job, as
highlighted in {numref}`fig-user-mode`. The following assumptions are made
throughout the rest of this user-mode installation discussion:

__Assumptions__:
* [ROCm](https://rocm.docs.amd.com/en/latest/) v6.1 or newer is pre-installed
  on all GPU hosts.
* Installer has access to a distributed file-system; if no distributed
  file-system is present, installation steps need to be repeated in all nodes.


## Omnistat software installation

To begin, we download the Omnistat software and install necessary Python
dependencies. Per the assumptions above, we clone and install Omnistat in a
path accessible from all nodes.

1. Clone repository.
   ```shell-session
   [user@login]$ git clone https://github.com/AMDResearch/omnistat.git
   ```

2. Install dependencies.
   ```shell-session
   [user@login]$ cd omnistat
   [user@login]$ pip install --user -r requirements.txt
   [user@login]$ pip install --user -r requirements-query.txt
   ```

```{note}
Omnistat can also be installed as a Python package. Create a virtual
environment, and install Omnistat and its dependencies from the top
directory of the cloned Omnistat repository.
```shell-session
[user@login]$ cd omnistat
[user@login]$ python -m venv ~/venv/omnistat
[user@login]$ ~/venv/omnistat/bin/python -m pip install .[query]
```

3. Download Prometheus. If `prometheus` isn't already installed in the system,
   download and extract a [precompiled binary](https://prometheus.io/download/).

## Configuring user-mode Omnistat

Omnistat provides a default configuration file,
[omnistat/config/omnistat.default](https://github.com/AMDResearch/omnistat/blob/main/omnistat/config/omnistat.default),
that will likely require modification to run in different environments.
The following lines highlighted in yellow may need to be customized.

```eval_rst
.. code-block:: ini
   :caption: Sample Omnistat configuration file
   :emphasize-lines: 2,8,11,12,13

    [omnistat.collectors]
    port = 8001
    enable_rocm_smi = True
    enable_rms = True

    [omnistat.collectors.rms]
    job_detection_mode = file-based
    job_detection_file = /tmp/omni_rmsjobinfo_user

    [omnistat.usermode]
    ssh_key = ~/.ssh/id_rsa
    prometheus_binary = /path/to/prometheus
    prometheus_datadir = data_prom
    prometheus_logfile = prom_server.log
  ```

## Running a SLURM Job

In the SLURM job script, add the following lines to start and stop the data
collection before and after running the application. Lines highlighted in
yellow need to be customized for different installation paths.

```eval_rst
.. code-block:: bash
   :emphasize-lines: 1-2
   :caption: SLURM job file using user-mode Omnistat with a 10 second sampling interval

    export OMNISTAT_CONFIG=/path/to/omnistat.config
    export OMNISTAT_DIR=/path/to/omnistat

    # Start data collector
    ${OMNISTAT_DIR}/omnistat-usermode --start --interval 10

    # Run application(s) as normal
    srun <options> ./a.out
    
    # End of job - generate summary report and stop data collection
    ${OMNISTAT_DIR}/omnistat-query --job ${SLURM_JOB_ID} --interval 10
    ${OMNISTAT_DIR}/omnistat-usermode --stop
  ```

## Exploring results with a local Docker environment

To explore results generated for user-mode executions of Omnistat, we provide
a Docker environment that will automatically launch the required services
locally. That includes Prometheus to read and query the stored data, and
Grafana as visualization platform to display time series and other metrics.

To explore results:

1. Copy Prometheus data collected with Omnistat to `./prometheus-data`. The
   entire `datadir` defined in the Omnistat configuration needs to be copied
   (e.g. a `data` directory should be present under `./prometheus-data`).
2. Start services:
   ```shell-session
   [user@login]$ export PROMETHEUS_USER="$(id -u):$(id -g)"
   [user@login]$ docker compose up -d
   ```
   User and group IDs are exported with the `PROMETHEUS_USER` variable to ensure
   the container has the right permissions to read the local data under the
   `./prometheus-data` directory.
4. Access Grafana dashboard at [http://localhost:3000](http://localhost:3000).
   Note that starting Grafana can take a few seconds.
5. Stop services:
   ```shell-session
   [user@login]$ docker compose down
   ```
